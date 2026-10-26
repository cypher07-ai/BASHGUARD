from coder import is_coding_request, detect_language

tests = [
    "write a snake game in python",
    "create a todo list app in javascript",
    "build a fibonacci calculator",
    "rm -rf /home",
    "delete all my files",
    "make a REST API in python using flask",
    "write me a tic tac toe game",
    "can you write a sorting algorithm in C++",
    "generate a password manager in python",
]

print("DETECTION TESTS:")
for t in tests:
    is_code = is_coding_request(t)
    lang = detect_language(t) if is_code else ("N/A", "", "")
    tag = "CODE" if is_code else "SKIP"
    print(f"  [{tag}] {t[:48]:<48} -> {lang[0]}")
