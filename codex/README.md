# Codex용 네이티브 Claude 스타일 statusline

Codex 0.153.4의 Ratatui `bottom_pane` 안에 Claude statusline과 같은 8칸 사용률 막대를
그립니다. 터미널 status bar나 tmux pane을 만들지 않으므로 채팅 영역의 위치와 종료 흐름을
바꾸지 않습니다.

```text
~/myproject · main · ctx ████████ 36% · 5h ████████ 66% (in 4m) · 7d ████████ 36% (in 5d21h) · gpt-5.6-sol · medium
```

막대는 사용률 60% 미만이면 초록, 60~84%면 노랑, 85% 이상이면 빨강입니다. 채워진 칸과
빈 칸 모두 `█`을 쓰고 빈 칸만 어둡게 표시합니다. `ctx`는 Codex가 이미 계산한 현재 turn의
`token_usage`와 model context window를 사용합니다. `5h`와 `7d`는 Codex가 계정 응답에서
유지하는 rate-limit snapshot을 사용하며, 초기화까지 남은 시간은 5초마다 다시 그립니다.
새 turn을 처리하는 동안에는 마지막으로 확인된 `ctx` 값을 유지하고, 첫 응답 전에는 어두운
8칸 막대와 `?`를 표시합니다. 따라서 토큰 집계를 기다리는 짧은 구간에도 항목과 레이아웃이
사라지지 않습니다.
계정 사용량은 statusline을 표시하는 각 ChatGPT 세션에서 60초마다 기존
`account/rateLimits/read`로 조회합니다. 따라서 다른 세션에서 사용한 양도 대기 중인
세션에 반영됩니다. 진행 중인 조회는 중복 실행하지 않으며 15초 timeout 또는 오류가
나면 마지막 사용량을 유지하고 다음 주기에 재시도합니다. 이 조회는 모델을 생성 호출하지
않습니다. `ctx`는 해당 세션의 값이므로 다른 세션의 작업으로 바뀌지 않습니다.

## 설치

Rust와 기존 Codex CLI 0.153.4가 필요합니다. 빌드는 OpenAI 공식 저장소의 정확한
`rust-v0.153.4` commit을 확인한 뒤 공개 patch만 적용합니다.

```sh
python3 codex/build_native.py
python3 codex/install.py
```

첫 명령은 패치된 바이너리를 `~/.local/share/codex-statusline/bin/codex`에 설치하고,
공식 standalone 0.153.4 패키지에 함께 들어 있는 `codex-code-mode-host`도 같은 `bin`
디렉터리에 복사합니다. statusline patch는 TUI에만 적용되므로 host는 수정하지 않지만,
Codex는 Code Mode를 시작할 때 실행 중인 본체 옆에서 이 파일을 찾습니다. 둘을 함께
설치하지 않으면 일반 채팅은 동작해도 Code Mode만 fail closed됩니다.
두 번째 명령은 `~/.local/bin/codex` launcher와 `[tui]`의 관리 대상 두 설정만 갱신합니다.
기존 config의 모델, 권한, 프로젝트 trust 등 다른 값은 보존합니다. launcher는 열린 파일 수
soft limit을 최대 4096으로 올린 뒤 패치된 Codex를 직접 `exec`합니다.

## 보안과 업데이트

- 인증 파일, `.env`, Keychain, 세션 JSONL, 대화 내용을 읽거나 복사하지 않습니다.
- 화면 값은 Codex 프로세스가 이미 보유한 메모리 상태만 사용하며 별도 API 호출이나 사용량
  파일을 만들지 않습니다.
- patch는 Codex 0.153.4 commit에 고정되어 있습니다. Codex를 업데이트하면 새 tag 기준으로
  patch를 다시 검토하고 빌드해야 합니다.
- 저장소에는 바이너리, 실제 계정 값, 경로, thread UUID를 올리지 않습니다.

## 검증

```sh
python3 -m unittest discover -s codex -p 'test_*.py'
```

Rust patch의 테스트는 upstream checkout에서 다음과 같이 실행합니다.

```sh
CARGO_PROFILE_TEST_DEBUG=0 CARGO_INCREMENTAL=0 \
  cargo test -p codex-tui compact_usage --lib
```
