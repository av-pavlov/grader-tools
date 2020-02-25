MARKER = r'[//]: # (INDIV)'

def build_badges():
	return "Возможно, со временем появится автоматическое тестирование индивидуальных заданий"

report = ""
for line in open("README.md", encoding="utf-8"):
	if MARKER in line:
		report += MARKER + ' ' + build_badges()
	else
		report += line

open("README.md", "w", encoding="utf-8").write(report)
