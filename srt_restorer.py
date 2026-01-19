"""
SRT 파일 일본어 복원기
- 히라가나/카타카나로 변환된 부분을 원래 한자/숫자로 복원
- 전체 맥락을 고려한 복원
"""

import json
from pathlib import Path
from srt_common import (
    get_client, load_rules, parse_srt, build_srt, get_full_context,
    ensure_srt_folders, get_corrected_path, get_restored_path,
    DEFAULT_MODEL, SRT_CORRECTED_FOLDER, SRT_RESTORED_FOLDER
)


def restore_readings_batch(client, entries, rules, model=DEFAULT_MODEL, batch_size=5):
    """
    배치로 읽기 복원 (히라가나/카타카나 → 한자/숫자)
    """
    full_context = get_full_context(entries)
    context_hints = "\n".join(rules.get("context_hints", []))
    reading_examples = json.dumps(rules.get("reading_examples", {}), ensure_ascii=False, indent=2)

    system_prompt = f"""あなたは日本語字幕の復元専門家です。

## 作業目標
ひらがなやカタカナで表記されている部分を、**適切な漢字や数字**に戻します。

## 全体の文脈
{full_context[:3000]}

## 文脈ヒント
{context_hints}

## 読み方の例（逆変換の参考）
{reading_examples}

## 詳細指示
1. **ひらがな→漢字**: 文脈に合った適切な漢字に変換
   - 例: ひょうやず → 表や図
   - 例: もとに → 基に
2. **ひらがな→数字**: 数字で表記すべき部分は数字に戻す
   - 例: よんじゅうに → 42
   - 例: せんななひゃくごじゅうおく → 1,750億
3. **カタカナ→英数字**: 技術用語は元の表記に戻す
   - 例: ワードツーベック → Word2Vec
   - 例: ジーピーティーフォー → GPT-4
   - 例: さんまるきゅうまる → 3090
4. **そのまま維持**: すでに適切な表記は変更しない
5. **日本語を維持**: 翻訳はせず、日本語テキストとして出力

## 応答形式
JSON形式: {{"1": "復元されたテキスト1", "2": "復元されたテキスト2", ...}}
"""

    restored_entries = []

    for batch_start in range(0, len(entries), batch_size):
        batch = entries[batch_start:batch_start + batch_size]

        batch_texts = {}
        for entry in batch:
            if entry['text'].strip():
                batch_texts[str(entry['index'])] = entry['text']

        if not batch_texts:
            restored_entries.extend([e.copy() for e in batch])
            continue

        user_prompt = f"""以下の日本語字幕を元の表記に復元してください。
ひらがな/カタカナを適切な漢字/数字/英字に戻してください。

{json.dumps(batch_texts, ensure_ascii=False, indent=2)}

JSON形式で復元されたテキストのみ応答してください。"""

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

            restorations = json.loads(response.choices[0].message.content)

            for entry in batch:
                new_entry = entry.copy()
                idx_str = str(entry['index'])
                if idx_str in restorations:
                    restored_text = restorations[idx_str]
                    new_entry['text'] = restored_text

                    # 변경된 경우 출력
                    if entry['text'] != restored_text:
                        try:
                            print(f"[{entry['index']}] 복원됨:")
                            print(f"  원본: {entry['text'][:50]}...")
                            print(f"  복원: {restored_text[:50]}...")
                        except UnicodeEncodeError:
                            print(f"[{entry['index']}] 복원됨 (출력 생략)")

                restored_entries.append(new_entry)

            print(f"배치 {batch_start//batch_size + 1}/{(len(entries)-1)//batch_size + 1} 완료")

        except Exception as e:
            print(f"배치 복원 오류: {e}")
            restored_entries.extend([e.copy() for e in batch])

    return restored_entries


def restore_srt_file(input_path, output_path=None, model=DEFAULT_MODEL, batch_size=5):
    """
    교정된 SRT 파일을 원상태로 복원 (히라가나/카타카나 → 한자/숫자)

    Args:
        input_path: 교정된 SRT 파일 경로 (srt_corrected 폴더에서 찾음)
        output_path: 출력 파일 경로 (없으면 srt_restored 폴더에 자동 생성)
        model: 사용할 모델
        batch_size: 배치 크기
    """
    # SRT 폴더 확인
    ensure_srt_folders()

    # 입력 파일 경로 처리 (srt_corrected 폴더에서)
    input_path = get_corrected_path(input_path)

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

    # 복원
    print("\n=== 원상태로 복원 중 ===")
    restored = restore_readings_batch(client, entries, rules, model, batch_size)
    print("=== 복원 완료 ===\n")

    # 결과 저장 (srt_restored 폴더에 저장)
    if output_path is None:
        input_p = Path(input_path)
        output_path = get_restored_path(f"{input_p.stem}_restored{input_p.suffix}")
    else:
        output_path = get_restored_path(output_path)

    result = build_srt(restored)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result)

    print(f"복원 완료: {output_path}")
    return output_path


# CLI 인터페이스
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(f"""
SRT 일본어 복원기 사용법:

  폴더 구조:
    {SRT_CORRECTED_FOLDER}/ - 교정된 파일 (히라가나/카타카나)
    {SRT_RESTORED_FOLDER}/  - 복원된 파일 (한자/숫자)

  복원하기 (히라가나/카타카나 → 한자/숫자):
    python srt_restorer.py <input.srt> [output.srt] [옵션]

    예시:
    python srt_restorer.py "강의_corrected.srt"
    # → srt_corrected/강의_corrected.srt 를 읽어서
    # → srt_restored/강의_corrected_restored.srt 로 저장

  옵션:
    --model <모델명>       사용할 모델
    --batch-size <숫자>    배치 크기 (기본: 5)
""")
        sys.exit(0)

    input_file = sys.argv[1]
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

    restore_srt_file(input_file, output_file, model=model, batch_size=batch_size)
