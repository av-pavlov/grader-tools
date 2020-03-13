MARKER = r'<!-- INDIV -->'

def build_badges():
	return "Возможно, со временем появится автоматическое тестирование индивидуальных заданий"

report = ""
changed = False
for line in open("README.md", encoding="utf-8"):
	if MARKER in line:
		replacement_line = f'{MARKER} {build_badges()}\n'
		if line != replacement_line:
			changed = True
		report += replacement_line
	else:
		report += line

if changed:
	open("README.md", "w", encoding="utf-8").write(report)
