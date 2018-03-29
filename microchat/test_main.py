from .define import NAME, PASSWORD
from .interface import InitAll
from .longlink import run

# 测试


def start(name, password):
    InitAll()
    run(name, password)
    return


if __name__ == "__main__":
    start(NAME, PASSWORD)
