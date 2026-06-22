f = open('templates/index.html', 'r')
lines = f.readlines()
f.close()

# First render function - add recIcon after recClass
for i, line in enumerate(lines):
    if 'const recClass = stock.recommendation' in line and 'BUY' in line and i < 800:
        if not any('recIcon' in l for l in lines[i:i+3]):
            rec_icon_line = "                            const recIcon = stock.recommendation === 'BUY' ? '\U0001f7e2' : stock.recommendation === 'HOLD LONG' ? '\U0001f7e1' : '\U0001f534';\n"
            lines.insert(i+1, rec_icon_line)
            print(f'Added recIcon at line {i+2}')
        break

# Second render function (renderScreenerResults)
for i, line in enumerate(lines):
    if 'const recClass = stock.recommendation' in line and 'BUY' in line and i > 1200:
        if not any('recIcon' in l for l in lines[i:i+3]):
            rec_icon_line = "                    const recIcon = stock.recommendation === 'BUY' ? '\U0001f7e2' : stock.recommendation === 'HOLD LONG' ? '\U0001f7e1' : '\U0001f534';\n"
            lines.insert(i+1, rec_icon_line)
            print(f'Added recIcon at line {i+2}')
        break

# Update recommendation cells to include icon
for i, line in enumerate(lines):
    if 'stock.recommendation ||' in line and 'recClass' in line and i < 800:
        lines[i] = line.replace('${stock.recommendation ||', '${recIcon} ${stock.recommendation ||')
        print(f'Updated rec cell at line {i+1}')
        break

for i, line in enumerate(lines):
    if 'stock.recommendation ||' in line and 'recClass' in line and i > 1200:
        lines[i] = line.replace('${stock.recommendation ||', '${recIcon} ${stock.recommendation ||')
        print(f'Updated rec cell at line {i+1}')
        break

f = open('templates/index.html', 'w')
f.writelines(lines)
f.close()
print('Done!')
