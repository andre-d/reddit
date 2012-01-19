import subprocess
import tempfile

class ConflictException(Exception):
    pass

def threeWayMerge(original, a, b):
    try:
        data = [a, original, b]
        files = []
        names = []
        for d in data:
            f = tempfile.NamedTemporaryFile()
            f.write(d)
            f.flush()
            names.append(f.name)
            files.append(f)
        try:
            final = subprocess.check_output(["diff3", "-a", "--merge"] + names)
        except subprocess.CalledProcessError:
            raise ConflictException()
    finally:
        for f in files:
            f.close()
    return final

if __name__ == "__main__":
    original = "Hello people of the human rance\n\nHow are you tday"
    a = "Hello people of the human rance\n\nHow are you today"
    b = "Hello people of the human race\n\nHow are you tday"
    print threeWayMerge(original, a, b)
