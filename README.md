# SRT 일본어 자막 교정/복원기

한국어 강의를 일본어 음성으로 변환한 SRT 자막 파일의 오류를 교정하고, 교정된 파일을 다시 원상태로 복원하는 도구입니다.

## 주요 기능

### 1. 교정 기능 (한자/숫자 → 히라가나/카타카나)
- 여러 발음이 가능한 숫자/한자를 히라가나/카타카나로 변환
- 음성 인식 오류 교정 (Faiss, GPT-4, Word2Vec 등)
- 한국어 혼입 부분을 일본어로 변환
- 전체 맥락을 고려한 교정

### 2. 복원 기능 (히라가나/카타카나 → 한자/숫자)
- 교정된 히라가나/카타카나를 원래 한자/숫자로 복원
- 기술 용어를 원래 표기로 복원

## 설치

```bash
pip install -r requirements.txt
```

## 환경 설정

`.env` 파일을 생성하고 Azure OpenAI 설정을 추가합니다:

```env
AZURE_ENDPOINT=your_azure_endpoint
AZURE_API_KEY=your_api_key
AZURE_API_VERSION=2024-08-01-preview
DEFAULT_MODEL=gpt-4o
```

## 폴더 구조

```
├── srt_common.py         # 공통 함수 모듈
├── srt_corrector.py      # 교정 스크립트
├── srt_restorer.py       # 복원 스크립트
├── correction_rules.json # 교정 규칙 파일
├── requirements.txt      # Python 의존성
├── .env                  # 환경 변수 (직접 생성 필요)
├── README.md             # 이 문서
├── srt_file/             # 원본 SRT 파일 폴더
│   └── 강의.srt
├── srt_corrected/        # 교정된 파일 폴더 (히라가나/카타카나)
│   └── 강의_corrected.srt
└── srt_restored/         # 복원된 파일 폴더 (한자/숫자)
    └── 강의_corrected_restored.srt
```

## 사용법

### 1. 교정하기 (한자/숫자 → 히라가나/카타카나)

원본 파일을 `srt_file` 폴더에 넣고 실행:

```bash
# 기본 사용
python srt_corrector.py "강의.srt"
# → srt_file/강의.srt 를 읽어서
# → srt_corrected/강의_corrected.srt 로 저장

# 출력 파일명 지정
python srt_corrector.py "강의.srt" "custom_output.srt"

# 배치 크기 지정 (한번에 여러 자막 처리)
python srt_corrector.py "강의.srt" --batch-size 10
```

### 2. 복원하기 (히라가나/카타카나 → 한자/숫자)

교정된 파일을 다시 원상태로 복원:

```bash
# 기본 사용
python srt_restorer.py "강의_corrected.srt"
# → srt_corrected/강의_corrected.srt 를 읽어서
# → srt_restored/강의_corrected_restored.srt 로 저장

# 출력 파일명 지정
python srt_restorer.py "강의_corrected.srt" "final.srt"

# 배치 크기 지정
python srt_restorer.py "강의_corrected.srt" --batch-size 10
```

### 3. 규칙 관리

#### 용어 교정 추가
```bash
python srt_corrector.py add-term "Face" "Faiss"
python srt_corrector.py add-term "GPT-4" "ジーピーティーフォー"
```

#### 맥락 힌트 추가
```bash
python srt_corrector.py add-hint "この講義はRAGに関する内容です"
```

#### 사용자 정의 규칙 추가
```bash
python srt_corrector.py add-rule "GPU型番は製品名として認識する"
```

#### 읽기 예시 추가
```bash
python srt_corrector.py add-reading "7日" "なのか"
python srt_corrector.py add-reading "基に" "もとに"
```

#### 현재 규칙 목록 확인
```bash
python srt_corrector.py list-rules
```

## 기본 제공 규칙

### 음성 인식 오류 교정
| 잘못 인식 | 올바른 표기 |
|----------|------------|
| Face, フェイス | Faiss |
| Lag, Leg | RAG |
| Hugging Faiss | Hugging Face |
| Word to Mac | ワードツーベック |
| 4o mini | フォーオー ミニ |

### 읽기 예시
| 표기 | 읽기 |
|-----|-----|
| 7日 | なのか |
| 1人 | ひとり |
| 2人 | ふたり |
| 表や図 | ひょうやず |
| 基に | もとに |
| Word2Vec | ワードツーベック |
| GPT-4 128K | ジーピーティーフォー いちにっぱちケー |
| 3090 | さんまるきゅうまる |

## 워크플로우 예시

```bash
# 1. 원본 파일을 srt_file 폴더에 복사
cp "원본강의.srt" srt_file/

# 2. 교정 실행 (한자/숫자 → 히라가나/카타카나)
python srt_corrector.py "원본강의.srt"
# → srt_corrected/원본강의_corrected.srt 생성

# 3. 교정된 파일로 영상 자막 작업

# 4. 필요시 복원 (히라가나/카타카나 → 한자/숫자)
python srt_restorer.py "원본강의_corrected.srt"
# → srt_restored/원본강의_corrected_restored.srt 생성
```

## 출력

- 전체 자막이 SRT 형식으로 출력됩니다 (수정된 부분 + 수정 안 된 부분 모두 포함)
- 바로 영상에 적용 가능한 형태로 저장됩니다
