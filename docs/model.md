# Model

## Architecture
<div align="center">
  <img src="images/gpt_block.png" height="250">
</div>

GPT 아키텍처 구현(`CausalSelfAttention`, `MLP`, `Block`, `GPT` 등 일부 클래스)은 [nanoGPT](https://github.com/karpathy/nanoGPT)(Andrej Karpathy, MIT License)를 기반으로 합니다. 토크나이저 확장, 학습 파이프라인, 생성 로직 등 나머지 구현은 프로젝트에 맞게 직접 구현했습니다.

- Decoder-only GPT, 12 layer / 12 head / 768 dim, 약 124.6M(1.246억 개) 파라미터
- block_size: 256
- Tokenizer: `skt/kogpt2-base-v2` 사용 + 로봇 명령/상태 관련 커스텀 토큰 추가 (vocab_size: 51,200)

> <sub>nanoGPT 원본 저작권 고지: Copyright (c) 2022 Andrej Karpathy — MIT License ([전문 보기](https://github.com/karpathy/nanoGPT/blob/master/LICENSE))

## Pretraining

### Training Environment

- Google Colab (A100 GPU)

### Data

| # | 데이터셋 | 출처 |
|---|---|---|
| 1 | 네이버 뉴스 요약 | [HuggingFace](https://huggingface.co/datasets/daekeun-ml/naver-news-summarization-ko/viewer/default/train?row=81) |
| 2 | 위키 문헌 | [HuggingFace](https://huggingface.co/datasets/wikimedia/wikisource/viewer/20231201.ko/train?p=2&row=290) |
| 3 | 도서자료 요약 | [AI Hub](https://www.aihub.or.kr/aihubdata/data/view.do?currMenu=115&topMenu=100&srchDataRealmCode=REALM002&aihubDataSe=data&dataSetSn=93) |
| 4 | 일반 상식 | [AI Hub](https://www.aihub.or.kr/aihubdata/data/view.do?currMenu=115&topMenu=100&srchDataRealmCode=REALM002&aihubDataSe=data&dataSetSn=106) |
| 5 | 한국어-영어 번역 말뭉치 <br><sub>(한국어 문장만 사용: 구어체(1)·(2), 대화체, 한국문화, 지자체웹사이트) | [AI Hub](https://www.aihub.or.kr/aihubdata/data/view.do?currMenu=115&topMenu=100&aihubDataSe=data&dataSetSn=126) |
| 6 | 한국어 성능이 개선된 초거대AI 언어모델 개발 및 데이터 <br><sub>("한국어 말뭉치 데이터" 사용) | [AI Hub](https://www.aihub.or.kr/aihubdata/data/view.do?currMenu=115&topMenu=100&srchDataRealmCode=REALM002&aihubDataSe=data&dataSetSn=71748) |

> <sub>**AI Hub 데이터셋 사용 안내**: 위 3~6번 데이터셋은 과학기술정보통신부와 한국지능정보사회진흥원(NIA)의 「지능정보산업 인프라 조성」 사업 결과물입니다. 이에 따라 한국지능정보사회진흥원의 사업 결과임을 밝히며, 데이터셋을 재배포하지 않고 본 리포지토리에는 원본 데이터를 포함하지 않습니다. 

### Corpus statistics

소스별 데이터 수 (train / val / test):

| 소스 | train | val | test |
|---|---:|---:|---:|
| 위키 문헌 | 24,112 | 497 | 249 |
| 네이버 뉴스 요약 | 21,528 | 443 | 223 |
| 일반 상식 | 66,481 | 1,370 | 687 |
| 한국어-영어 번역 말뭉치 | 606,961 | 12,514 | 6,258 |
| 도서자료 요약 | 155,201 | 3,200 | 1,601 |
| 한국어 말뭉치 데이터 | 2,608,302 | 53,779 | 26,891 |
| **합계** | **3,482,585** | **71,803** | **35,909** |

토큰화 결과 (KoGPT2 tokenizer 기준):

| | train | val | test |
|---|---:|---:|---:|
| 토큰 수 | 3,478,810,175 | 71,775,427 | 36,505,986 |

총 약 **3.59B(35.9억) 토큰**으로 사전학습을 진행했습니다.

### Result & Training curve

<img src="images/pretraining_loss_curve.png" width="700">

<img src="images/pretraining_loss_curve_zoom.png" width="700">

최종 test loss: **2.9331**

### Sample outputs

아래는 두 번 실행한 예시입니다.
<br>문법적으로 자연스러운 문장을 생성하지만, 사실관계 오류가 있으며 다소 엉뚱한 답변이 섞여 있습니다.

<div align="center">
  <img src="images/pretraining_sample_outputs_1.png" width="400">
  <img src="images/pretraining_sample_outputs_2.png" width="400">
</div>

## Fine tuning
