# Codex용 Claude 스타일 statusline

기존 Claude 표시기의 8칸 `█`, 초록/노랑/빨강 경계(60%·85%), 어두운 빈칸,
파란 Git 브랜치, 노란 변경 표시, 청록색 effort, `·` 구분자와 카운트다운을 재현합니다.

```text
~/myproject git:(main) * · ctx ████████ 36% · 5h ████████ 66% (in 4m) · 7d ████████ 36% (in 5d21h) · $62.95 · Codex · xhigh
```

위 수치는 가상 데모입니다. 실제 데이터를 캡처한 예시가 아닙니다.

## 지원 범위

Codex CLI 0.153.4의 내장 `tui.status_line`은 항목 목록만 받습니다. Claude처럼
셸 스크립트의 ANSI 출력을 직접 넣을 수 없습니다. `config.snippet.toml`은 내장 바의
항목 순서를 맞추며, 동일한 디자인은 별도 한 줄 tmux pane에서 표시합니다.
Codex 바이너리나 TUI 화면 출력을 수정하지 않습니다.

실제 5h/7d 사용량은 Codex app-server의 계정 조회를 사용합니다. 활성 thread UUID를
지정하면 모델/effort/작업 폴더를 읽습니다. 컨텍스트는 로컬 로그 끝의 숫자 토큰 정보로
계산한 근사치이며 Codex 내장 계산과 차이가 날 수 있습니다. 읽을 수 없으면 `?`입니다.
달러 비용은 이 인터페이스에서 신뢰할 수 있게 얻지 못하므로 `$?`로 표시합니다.
내장 `estimated-thread-cost`는 그대로 사용할 수 있습니다. 임의 비용을 계산하지 않습니다.
5시간·7일 사용량 뒤에는 Claude와 같은 상대 카운트다운을 표시합니다. 예를 들어
`(in 4h11m)`은 4시간 11분 뒤에 해당 창이 초기화된다는 뜻입니다. 이미 초기화된 창이나
2분 넘게 갱신되지 않은 값은 이전 사용량을 현재 값처럼 보여주지 않고 `?`로 바꿉니다.

## 설치

Python 3.9+, 설치된 Codex CLI, tmux가 필요합니다. 저장소를 받은 뒤 다음을 실행합니다.

```sh
python3 codex/install.py
python3 ~/.local/share/codex-statusline/statusline.py --demo
```

설치기는 명시된 소스 파일만 복사하고 기존 Codex 실행 symlink를 백업합니다.
다음부터 `codex`를 직접 실행해도 열린 파일 수 soft limit을 최대 4096까지 높입니다.
hard limit과 시스템 전체 설정은 바꾸지 않습니다. 현재 실행 중인 프로세스에는
적용되지 않으므로 현재 TUI를 종료하고 새 `codex` 프로세스를 시작해야 합니다.
터미널에서 평소처럼 `codex`를 실행하거나 `codex resume THREAD_UUID`로 재개하면, 별도
tmux 내부가 아닌 경우 하단의 Claude 스타일 pane도 자동으로 붙습니다. 새 대화는 계정의
5h/7d 사용량과 초기화 카운트다운을 즉시 표시하고, thread별 context·model·effort는 위쪽
Codex 내장 줄에 표시합니다. 기존 대화를 UUID로 재개하면 하단 줄에도 thread 값을 표시합니다.
현재 실행 중인 TUI는 다시 부모를 붙일 수 없으므로 재시작 전까지 기존 내장 바만 보입니다.

실제 한 줄 조회:

```sh
python3 ~/.local/share/codex-statusline/live.py --thread THREAD_UUID
```

하단 바를 붙여 기존 대화 재개:

```sh
python3 ~/.local/share/codex-statusline/launch.py THREAD_UUID
```

별도 `codex-statusline` tmux 서버를 사용합니다. `Ctrl+B`, `D`로 분리해도 대화는
종료하지 않습니다. 좁은 창은 하단 바의 오른쪽 항목을 자를 수 있습니다.

## 보안과 데이터

- 인증 파일·환경 파일·키체인을 직접 읽거나 복사하지 않습니다. 로그인은 Codex가 처리합니다.
- 계정 응답은 메모리에서 필요한 숫자만 사용하며, 파일 캐시나 네트워크 업로드는 없습니다.
- 컨텍스트 확인은 지정된 Codex sessions 경로의 로그 끝 최대 2 MiB만 메모리에서 읽습니다.
  대화 내용은 표시하거나 저장하지 않습니다. thread 전체 대화를 API로 요청하지 않습니다.
- 프로젝트 경로와 Git 브랜치는 로컬 화면에만 표시합니다. 화면 캡처 공유 시 주의하세요.
- 터미널 제어문자는 동적인 경로·브랜치·모델 문자열에서 제거합니다.
- 공개 파일에는 실행 로그, 실제 UUID, 계정 식별자, 사용량 캐시, 개인 config를 포함하지 않습니다.

## 검증

```sh
python3 -m unittest discover -s codex -p 'test_*.py'
python3 codex/statusline.py --demo --no-color
```

공식 설정: https://learn.chatgpt.com/docs/config-file/config-reference
