# 액션 1개를 표현하는 제네릭 struct
# type 값에 따라 유효한 필드만 채워지고 나머지는 기본값(빈 문자열 / -1)으로 둠

# type == "search"  -> target
# type == "move"    -> dir, speed, time, repeat
# type == "perform" -> action, speed, time, repeat
# type == "stop"    -> time, repeat
# type == "resume"  -> (필드 없음)

string type            # search/move/perform/stop/resume

string target           # search: COCO 80개 클래스 영문명

string dir              # move: forward/backward/left/right

string speed            # move, perform: slow/normal/fast

string action            # perform: dance/circle/spin/bow

# time/repeat 생략 시 -1, 로봇 노드에서 -1이면 기본값(time=5, repeat=1) 적용
int32 time
int32 repeat
