"""
model_server_node에서 사용하는 모델 로딩/생성 유틸
"""

import re
import math
from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import PreTrainedTokenizerFast
import sys


# COCO 80개 클래스 (RobotCommand의 search target으로 쓰이는 영문명)
COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
    "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack",
    "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
    "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
    "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator",
    "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush",
]

CUSTOM_TOKENS = [
    "search", "move", "perform", "stop", "resume",
    "dir", "speed", "time", "action", "repeat",
    "forward", "backward", "left", "right",
    "slow", "normal", "fast",
    "dance", "circle", "spin", "bow",
    "(", ")", "=", ",", ">",
    "result", "success", "fail", "not_found",
] + COCO_CLASSES

# GPT 모델 정의
@dataclass
class GPTConfig:
    vocab_size: int = 51200
    block_size: int = 256
    n_layer: int = 12
    n_head: int = 12
    n_embd: int = 768
    dropout: float = 0.1
    bias: bool = True


class CausalSelfAttention(nn.Module):
    def __init__(self, config):
        super().__init__()
        assert config.n_embd % config.n_head == 0
        self.n_head = config.n_head
        self.n_embd = config.n_embd

        self.c_attn = nn.Linear(config.n_embd, 3 * config.n_embd, bias=config.bias)
        self.c_proj = nn.Linear(config.n_embd, config.n_embd, bias=config.bias)

        self.attn_dropout = nn.Dropout(config.dropout)
        self.resid_dropout = nn.Dropout(config.dropout)

        self.register_buffer(
            "bias",
            torch.tril(torch.ones(config.block_size, config.block_size))
                 .view(1, 1, config.block_size, config.block_size)
        )

    def forward(self, x):
        B, T, C = x.size()

        q, k, v = self.c_attn(x).split(self.n_embd, dim=2)
        k = k.view(B, T, self.n_head, C // self.n_head).transpose(1, 2)
        q = q.view(B, T, self.n_head, C // self.n_head).transpose(1, 2)
        v = v.view(B, T, self.n_head, C // self.n_head).transpose(1, 2)

        att = (q @ k.transpose(-2, -1)) * (1.0 / math.sqrt(k.size(-1)))
        att = att.masked_fill(self.bias[:, :, :T, :T] == 0, float('-inf'))
        att = F.softmax(att, dim=-1)
        att = self.attn_dropout(att)

        y = att @ v
        y = y.transpose(1, 2).contiguous().view(B, T, C)
        y = self.resid_dropout(self.c_proj(y))
        return y


class MLP(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.c_fc = nn.Linear(config.n_embd, 4 * config.n_embd, bias=config.bias)
        self.gelu = nn.GELU()
        self.c_proj = nn.Linear(4 * config.n_embd, config.n_embd, bias=config.bias)
        self.dropout = nn.Dropout(config.dropout)

    def forward(self, x):
        x = self.c_fc(x)
        x = self.gelu(x)
        x = self.dropout(x)
        x = self.c_proj(x)
        return x


class Block(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.ln_1 = nn.LayerNorm(config.n_embd, bias=config.bias)
        self.attn = CausalSelfAttention(config)
        self.ln_2 = nn.LayerNorm(config.n_embd, bias=config.bias)
        self.mlp = MLP(config)

    def forward(self, x):
        x = x + self.attn(self.ln_1(x))
        x = x + self.mlp(self.ln_2(x))
        return x


class GPT(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.config = config

        self.transformer = nn.ModuleDict(dict(
            wte=nn.Embedding(config.vocab_size, config.n_embd),
            wpe=nn.Embedding(config.block_size, config.n_embd),
            drop=nn.Dropout(config.dropout),
            h=nn.ModuleList([Block(config) for _ in range(config.n_layer)]),
            ln_f=nn.LayerNorm(config.n_embd, bias=config.bias),
        ))
        self.lm_head = nn.Linear(config.n_embd, config.vocab_size, bias=False)
        self.transformer.wte.weight = self.lm_head.weight

        self.apply(self._init_weights)
        for pn, p in self.named_parameters():
            if pn.endswith('c_proj.weight'):
                torch.nn.init.normal_(p, mean=0.0, std=0.02 / math.sqrt(2 * config.n_layer))

    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                torch.nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def forward(self, idx, targets=None):
        device = idx.device
        b, t = idx.size()
        assert t <= self.config.block_size, f"시퀀스 길이 {t}가 block_size {self.config.block_size}를 초과함"

        pos = torch.arange(0, t, dtype=torch.long, device=device)
        tok_emb = self.transformer.wte(idx)
        pos_emb = self.transformer.wpe(pos)
        x = self.transformer.drop(tok_emb + pos_emb)

        for block in self.transformer.h:
            x = block(x)
        x = self.transformer.ln_f(x)
        logits = self.lm_head(x)

        loss = None
        if targets is not None:
            loss = F.cross_entropy(
                logits.view(-1, logits.size(-1)),
                targets.view(-1),
                ignore_index=-100,
            )
        return logits, loss


# 토큰 임베딩 확장 (신규 토큰만 랜덤 초기화, 기존 임베딩 보존)
def resize_token_embeddings(model: GPT, new_vocab_size: int) -> GPT:
    old_embeddings = model.transformer.wte.weight.data
    old_vocab_size, n_embd = old_embeddings.shape
    if new_vocab_size <= old_vocab_size:
        return model

    new_wte = nn.Embedding(new_vocab_size, n_embd)
    new_wte.weight.data.normal_(mean=0.0, std=0.02)
    new_wte.weight.data[:old_vocab_size] = old_embeddings

    model.transformer.wte = new_wte
    model.lm_head.weight = model.transformer.wte.weight  # weight tying 유지
    model.config.vocab_size = new_vocab_size
    return model

# 토크나이저 세팅
def load_tokenizer():
    tokenizer = PreTrainedTokenizerFast.from_pretrained("skt/kogpt2-base-v2")

    special_tokens = {}
    if tokenizer.eos_token is None:
        special_tokens['eos_token'] = '</s>'
    if tokenizer.bos_token is None:
        special_tokens['bos_token'] = '<s>'
    if tokenizer.pad_token is None:
        special_tokens['pad_token'] = '<pad>'
    if tokenizer.unk_token is None:
        special_tokens['unk_token'] = '<unk>'
    tokenizer.add_special_tokens(special_tokens)

    tokenizer.add_tokens(CUSTOM_TOKENS)
    return tokenizer

# 모델 로딩
def load_model(checkpoint_path: str, tokenizer, device: str):
    main_module = sys.modules['__main__']
    if not hasattr(main_module, 'GPTConfig'):
        main_module.GPTConfig = GPTConfig

    config = GPTConfig(vocab_size=len(tokenizer))
    model = GPT(config)
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.to(device)
    model.eval()
    return model

# 생성 (greedy 기본, do_sample=True면 temperature 샘플링)
@torch.no_grad()
def generate(model: GPT, tokenizer, prompt: str, device: str,
             max_new_tokens: int = 64, do_sample: bool = False, temperature: float = 1.0) -> str:
    block_size = model.config.block_size
    eos_id = tokenizer.eos_token_id

    ids = tokenizer.encode(prompt, add_special_tokens=False)
    ids = torch.tensor(ids, dtype=torch.long, device=device).unsqueeze(0)
    prompt_len = ids.size(1)

    for _ in range(max_new_tokens):
        idx_cond = ids if ids.size(1) <= block_size else ids[:, -block_size:]
        logits, _ = model(idx_cond)
        logits = logits[:, -1, :] / max(temperature, 1e-5)

        if do_sample:
            probs = F.softmax(logits, dim=-1)
            next_id = torch.multinomial(probs, num_samples=1)
        else:
            next_id = torch.argmax(logits, dim=-1, keepdim=True)

        ids = torch.cat([ids, next_id], dim=1)
        if next_id.item() == eos_id:
            break

    generated_ids = ids[0, prompt_len:].tolist()
    if generated_ids and generated_ids[-1] == eos_id:
        generated_ids = generated_ids[:-1]

    text = tokenizer.decode(generated_ids)
    text = re.sub(r'([=(])\s+', r'\1', text)  # decode 아티팩트 후처리
    return text.strip()
