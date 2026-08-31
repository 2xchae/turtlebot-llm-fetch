# fetch_robot_node가 액션 1개 실행을 마칠 때마다 발행
# response_generator_node가 feedback을 받음
string type            # search/move/perform/stop/resume

string target           # search에서만 사용

string dir              # move에서만 사용

string action            # perform에서만 사용

string result            # search: success/fail/not_found
                          # move/perform/resume: success/fail
                          # stop: success
