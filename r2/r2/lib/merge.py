import subprocess
import tempfile
import difflib
from pylons.i18n import _

class ConflictException(Exception):
    def __init__(self, new, your, original):
        self.your = your
        self.new = new
        self.original = original
        self.htmldiff = make_htmldiff(new, your, _("Current edit"), _("Your edit"))
        Exception.__init__(self)


def make_htmldiff(a, b, adesc, bdesc):
    diffcontent = difflib.HtmlDiff()
    return diffcontent.make_table(a.splitlines(),
                                  b.splitlines(),
                                  fromdesc=adesc,
                                  todesc=bdesc)

def threeWayMerge(original, a, b):
    try:
        data = [a, original, b]
        files = []
        names = []
        for d in data:
            f = tempfile.NamedTemporaryFile(dir='/dev/shm')
            f.write(d)
            f.flush()
            names.append(f.name)
            files.append(f)
        try:
            final = subprocess.check_output(["diff3", "-a", "--merge"] + names)
        except subprocess.CalledProcessError:
            raise ConflictException(b, a, original)
    finally:
        for f in files:
            f.close()
    return final

if __name__ == "__main__":
    original = "Hello people of the human rance\n\nHow are you tday"
    a = "Hello people of the human rance\n\nHow are you today"
    b = "Hello people of the human race\n\nHow are you tday"
    print threeWayMerge(original, a, b)
