"""
SRT 파일 일본어 교정기
- 여러 발음으로 읽힐 수 있는 숫자/한자를 히라가나/카타카나로 변환
- 전체 맥락을 고려한 교정
- 사용자 정의 규칙 적용
"""

import json
from pathlib import Path
from srt_common import (
    get_client, load_rules, parse_srt, build_srt, get_full_context,
    ensure_srt_folders, get_input_path, get_corrected_path,
    add_rule, remove_rule, list_rules,
    DEFAULT_MODEL, SRT_INPUT_FOLDER, SRT_CORRECTED_FOLDER
)


def apply_term_corrections(text, rules):
    """용어 교정 규칙 적용"""
    for wrong, correct in rules.get("term_corrections", {}).items():
        text = text.replace(wrong, correct)
    return text


def correct_readings_batch(client, entries, rules, model=DEFAULT_MODEL, batch_size=5):
    """
    배치로 읽기 교정 (일본어 유지, 여러 발음 부분만 히라가나/카타카나로)
    """
    full_context = get_full_context(entries)
    context_hints = "\n".join(rules.get("context_hints", []))
    custom_rules = "\n".join(rules.get("custom_rules", []))
    reading_examples = json.dumps(rules.get("reading_examples", {}), ensure_ascii=False, indent=2)

    system_prompt = f"""あなたは日本語字幕の校正専門家です。

## 作業目標
日本語テキストをそのまま維持しつつ、**複数の読み方（発音）が可能な数字や漢字**のみを
実際の音声で発音される**ひらがなまたはカタカナ**に変換します。

## 全体の文脈
{full_context[:3000]}

## 文脈ヒント
{context_hints}

## 変換ルール
{custom_rules}

## 読み方の例
{reading_examples}

## 詳細指示
1. **日本語はそのまま維持**: 翻訳しないでください。日本語テキストをそのまま出力します。
2. **複数の読み方がある場合のみ変換**:
   - 数字: 42 → よんじゅうに, 1,750億 → せんななひゃくごじゅうおく
   - カンマ区切りの数字: 2,000 → にせん (カンマを無視)
   - 漢字: 複数の音読み/訓読みがある場合、文脈に合った読み方で
   - 日付: 7日 → なのか, 1日 → ついたち
   - 人数: 1人 → ひとり, 2人 → ふたり
3. **読み方が明確なものはそのまま維持**: 無理にひらがなに変換する必要なし
4. **音声認識エラーの修正**:
   - 「Face」「フェイス」→「Faiss」（ベクトル検索ライブラリ）
   - 「GPT 4」→「ジーピーティーフォー」
   - 「3090」「さんぜんきゅうじゅう」→「さんまるきゅうまる」（GPU型番）
   - 「Word to Mac」→「Word2Vec」
5. **技術用語は正確に**: AI/ML関連の専門用語は正しい表記に修正
6. **韓国語（ハングル）の処理**:
   - ハングル文字が混在している場合は、前後の文脈から適切な日本語に翻訳
   - 例: "ホワイト 해설 액ト" → "Pytesseract"

## 応答形式
JSON形式: {{"1": "校正されたテキスト1", "2": "校正されたテキスト2", ...}}
"""

    corrected_entries = []

    for batch_start in range(0, len(entries), batch_size):
        batch = entries[batch_start:batch_start + batch_size]

        batch_texts = {}
        for entry in batch:
            if entry['text'].strip():
                batch_texts[str(entry['index'])] = entry['text']

        if not batch_texts:
            corrected_entries.extend([e.copy() for e in batch])
            continue

        user_prompt = f"""以下の日本語字幕を校正してください。
複数の発音が可能な数字/漢字のみひらがな/カタカナに変換し、その他はそのまま維持してください。

{json.dumps(batch_texts, ensure_ascii=False, indent=2)}

JSON形式で校正されたテキストのみ応答してください。"""

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )

            corrections = json.loads(response.choices[0].message.content)

            for entry in batch:
                new_entry = entry.copy()
                idx_str = str(entry['index'])
                if idx_str in corrections:
                    corrected_text = corrections[idx_str]
                    corrected_text = apply_term_corrections(corrected_text, rules)
                    new_entry['text'] = corrected_text

                    # 변경된 경우 출력
                    if entry['text'] != corrected_text:
                        print(f"[{entry['index']}] 교정됨:")
                        print(f"  원본: {entry['text'][:50]}...")
                        print(f"  교정: {corrected_text[:50]}...")

                corrected_entries.append(new_entry)

            print(f"배치 {batch_start//batch_size + 1}/{(len(entries)-1)//batch_size + 1} 완료")

        except Exception as e:
            print(f"배치 교정 오류: {e}")
            print(f"오류 타입: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            corrected_entries.extend([e.copy() for e in batch])

    return corrected_entries


def correct_srt_file(input_path, output_path=None, model=DEFAULT_MODEL, batch_size=5):
    """
    SRT 파일 교정 메인 함수

    Args:
        input_path: 입력 SRT 파일 경로 (파일명만 입력시 srt_file 폴더에서 찾음)
        output_path: 출력 파일 경로 (없으면 srt_corrected 폴더에 자동 생성)
        model: 사용할 모델
        batch_size: 배치 크기
    """
    # SRT 폴더 확인
    ensure_srt_folders()

    # 입력 파일 경로 처리
    input_path = get_input_path(input_path)

    # Azure OpenAI 클라이언트 초기화
    client = get_client()

    # 파일 읽기
    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 파싱
    entries = parse_srt(content)
    print(f"총 {len(entries)}개의 자막 항목 발견")
    print(f"모델: {model}")

    # 규칙 로드
    rules = load_rules()

    # 교정
    print("\n=== 읽기 교정 중 ===")
    corrected = correct_readings_batch(client, entries, rules, model, batch_size)
    print("=== 교정 완료 ===\n")

    # 결과 저장 (srt_corrected 폴더에 저장)
    if output_path is None:
        input_p = Path(input_path)
        output_path = get_corrected_path(f"{input_p.stem}_corrected{input_p.suffix}")
    else:
        output_path = get_corrected_path(output_path)

    result = build_srt(corrected)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result)

    print(f"교정 완료: {output_path}")
    return output_path


# CLI 인터페이스
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(f"""
SRT 일본어 교정기 사용법:

  폴더 구조:
    {SRT_INPUT_FOLDER}/     - 원본 파일
    {SRT_CORRECTED_FOLDER}/ - 교정된 파일 (히라가나/카타카나)

  교정하기 (한자/숫자 → 히라가나/카타카나):
    python srt_corrector.py <input.srt> [output.srt] [옵션]

    예시:
    python srt_corrector.py "강의.srt"
    # → srt_file/강의.srt 를 읽어서
    # → srt_corrected/강의_corrected.srt 로 저장

  옵션:
    --model <모델명>       사용할 모델
    --batch-size <숫자>    배치 크기 (기본: 5)

  규칙 관리:
    python srt_corrector.py add-term "잘못된용어" "올바른용어"
    python srt_corrector.py add-hint "맥락 힌트 내용"
    python srt_corrector.py add-rule "사용자 정의 규칙"
    python srt_corrector.py add-reading "42" "よんじゅうに"
    python srt_corrector.py remove-term "용어"
    python srt_corrector.py list-rules
""")
        sys.exit(0)

    command = sys.argv[1]

    # 규칙 관리 명령어
    if command == "add-term":
        add_rule("term", sys.argv[2], sys.argv[3])
    elif command == "add-hint":
        add_rule("hint", sys.argv[2])
    elif command == "add-rule":
        add_rule("custom", sys.argv[2])
    elif command == "add-reading":
        add_rule("reading", sys.argv[2], sys.argv[3])
    elif command == "remove-term":
        remove_rule("term", sys.argv[2])
    elif command == "remove-reading":
        remove_rule("reading", sys.argv[2])
    elif command == "list-rules":
        list_rules()
    else:
        # 교정 명령어 (파일명)
        input_file = command
        output_file = None
        model = DEFAULT_MODEL
        batch_size = 5

        # 옵션 파싱
        i = 2
        while i < len(sys.argv):
            arg = sys.argv[i]
            if arg == "--model" and i + 1 < len(sys.argv):
                model = sys.argv[i + 1]
                i += 2
            elif arg == "--batch-size" and i + 1 < len(sys.argv):
                batch_size = int(sys.argv[i + 1])
                i += 2
            elif not arg.startswith("--"):
                output_file = arg
                i += 1
            else:
                i += 1

        correct_srt_file(input_file, output_file, model=model, batch_size=batch_size)
