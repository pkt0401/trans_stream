"""
SRT 파일 처리 공통 함수들
"""

import re
import json
import os
from openai import AzureOpenAI
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# Azure OpenAI 설정
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT")
AZURE_API_KEY = os.getenv("AZURE_API_KEY")
AZURE_API_VERSION = os.getenv("AZURE_API_VERSION")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL")

# 설정 파일 경로
RULES_FILE = "correction_rules.json"

# SRT 파일 기본 경로
SRT_INPUT_FOLDER = "srt_file"          # 원본 파일
SRT_CORRECTED_FOLDER = "srt_corrected"  # 교정된 파일 (히라가나/카타카나)
SRT_RESTORED_FOLDER = "srt_restored"    # 복원된 파일 (원상태)


def get_client():
    """Azure OpenAI 클라이언트 생성"""
    return AzureOpenAI(
        azure_endpoint=AZURE_ENDPOINT,
        api_key=AZURE_API_KEY,
        api_version=AZURE_API_VERSION
    )


def load_rules():
    """교정 규칙 파일 로드"""
    if os.path.exists(RULES_FILE):
        with open(RULES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "context_hints": [
            "この講義はRAG（Retrieval-Augmented Generation）に関する内容です。",
            "AI、機械学習、自然言語処理関連の用語が頻繁に登場します。"
        ],
        "custom_rules": [
            "数字に複数の読み方がある場合は、実際に発音されるひらがなに変換する",
            "漢字に複数の読み方がある場合は、文脈に合ったひらがなに変換する",
        ],
        "reading_examples": {
            "42": "よんじゅうに",
            "7日": "なのか",
            "1人": "ひとり",
        }
    }


def save_rules(rules):
    """교정 규칙 파일 저장"""
    with open(RULES_FILE, "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)


def parse_srt(content):
    """SRT 파일 파싱"""
    entries = []
    blocks = re.split(r'\n\n+', content.strip())

    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 2:
            try:
                index = int(lines[0])
                timestamp = lines[1]
                text = '\n'.join(lines[2:]) if len(lines) > 2 else ""
                entries.append({
                    "index": index,
                    "timestamp": timestamp,
                    "text": text
                })
            except ValueError:
                continue

    return entries


def build_srt(entries):
    """SRT 형식으로 재구성"""
    result = []
    for entry in entries:
        result.append(f"{entry['index']}")
        result.append(entry['timestamp'])
        result.append(entry['text'])
        result.append("")
    return '\n'.join(result)


def get_full_context(entries):
    """전체 내용에서 맥락 추출"""
    full_text = " ".join([e['text'] for e in entries])
    return full_text


def ensure_srt_folders():
    """SRT 폴더들이 없으면 생성"""
    for folder in [SRT_INPUT_FOLDER, SRT_CORRECTED_FOLDER, SRT_RESTORED_FOLDER]:
        if not os.path.exists(folder):
            os.makedirs(folder)
            print(f"'{folder}' 폴더를 생성했습니다.")


def get_input_path(filename):
    """입력 파일의 전체 경로 반환 (srt_file 폴더 기준)"""
    if os.path.isabs(filename) or os.path.exists(filename):
        return filename
    return os.path.join(SRT_INPUT_FOLDER, filename)


def get_corrected_path(filename):
    """교정된 파일의 전체 경로 반환 (srt_corrected 폴더)"""
    if os.path.isabs(filename):
        return filename
    return os.path.join(SRT_CORRECTED_FOLDER, filename)


def get_restored_path(filename):
    """복원된 파일의 전체 경로 반환 (srt_restored 폴더)"""
    if os.path.isabs(filename):
        return filename
    return os.path.join(SRT_RESTORED_FOLDER, filename)


def add_rule(rule_type, key, value=None):
    """규칙 추가"""
    rules = load_rules()

    if rule_type == "term":
        rules.setdefault("term_corrections", {})[key] = value
        print(f"용어 교정 추가: {key} → {value}")
    elif rule_type == "hint":
        if key not in rules.get("context_hints", []):
            rules.setdefault("context_hints", []).append(key)
            print(f"맥락 힌트 추가: {key}")
    elif rule_type == "custom":
        if key not in rules.get("custom_rules", []):
            rules.setdefault("custom_rules", []).append(key)
            print(f"사용자 규칙 추가: {key}")
    elif rule_type == "reading":
        rules.setdefault("reading_examples", {})[key] = value
        print(f"읽기 예시 추가: {key} → {value}")

    save_rules(rules)
    return rules


def remove_rule(rule_type, key):
    """규칙 제거"""
    rules = load_rules()

    if rule_type == "term" and key in rules.get("term_corrections", {}):
        del rules["term_corrections"][key]
        print(f"용어 교정 제거: {key}")
    elif rule_type == "hint" and key in rules.get("context_hints", []):
        rules["context_hints"].remove(key)
        print(f"맥락 힌트 제거: {key}")
    elif rule_type == "custom" and key in rules.get("custom_rules", []):
        rules["custom_rules"].remove(key)
        print(f"사용자 규칙 제거: {key}")
    elif rule_type == "reading" and key in rules.get("reading_examples", {}):
        del rules["reading_examples"][key]
        print(f"읽기 예시 제거: {key}")

    save_rules(rules)
    return rules


def list_rules():
    """현재 규칙 목록 출력"""
    rules = load_rules()

    print("\n=== 현재 교정 규칙 ===\n")

    print("[용어 교정]")
    for wrong, correct in rules.get("term_corrections", {}).items():
        print(f"  {wrong} → {correct}")

    print("\n[맥락 힌트]")
    for hint in rules.get("context_hints", []):
        print(f"  - {hint}")

    print("\n[사용자 규칙]")
    for rule in rules.get("custom_rules", []):
        print(f"  - {rule}")

    print("\n[읽기 예시]")
    for char, reading in rules.get("reading_examples", {}).items():
        print(f"  {char} → {reading}")

    return rules
