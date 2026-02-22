"""
지뢰찾기 실행 및 오류 진단 스크립트
실행: python __task.py
"""
import subprocess
import sys
import os

TARGET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "minesweeper.py")

print(f"[실행] {TARGET}")
print(f"[Python] {sys.executable}")
print("─" * 50)

try:
    result = subprocess.run(
        [sys.executable, TARGET],
        capture_output=False,  # 화면에 바로 출력
    )
    if result.returncode != 0:
        print(f"\n[종료 코드] {result.returncode}")
except FileNotFoundError as e:
    print(f"[오류] 파일을 찾을 수 없습니다: {e}")
except Exception as e:
    print(f"[오류] {type(e).__name__}: {e}")
finally:
    print("\n─" * 25)
    os.system("pause")
