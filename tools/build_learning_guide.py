import json,html,textwrap
from pathlib import Path
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,PageBreak,Table,TableStyle
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
ROOT=Path(__file__).resolve().parents[1]
d=json.loads((ROOT/'docs/learning-guide-source.json').read_text(encoding='utf-8'))
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='BodyGuide',fontName='Helvetica',fontSize=10.5,leading=15,spaceAfter=9))
styles.add(ParagraphStyle(name='CodeGuide',fontName='Courier',fontSize=8,leading=11,spaceAfter=12,wordWrap='CJK'))
styles.add(ParagraphStyle(name='CellGuide',fontName='Helvetica',fontSize=9,leading=12,spaceAfter=0))
styles['Title'].textColor=colors.black
styles['Heading1'].textColor=colors.black
styles['Heading1'].fontSize=20
styles['Heading1'].leading=25
styles['Heading2'].textColor=colors.black
def esc(s):return html.escape(s).replace('\u2013','-').replace('\u2014','-')
def para(s,style='BodyGuide'):return Paragraph(esc(s),styles[style])
story=[para(d['title'],'Title'),Spacer(1,15),para(d['subtitle']),para(d['date']),Spacer(1,20),para(d['intro']),Spacer(1,15),para('How to use this guide','Heading2'),para('Read sections 1 to 3 for the story and vocabulary. Sections 4 to 17 explain the build stages. Section 18 teaches report reading. Sections 19 to 22 contain commands and troubleshooting. Sections 23 to 25 prepare you for mentor questions. Sections 26 to 28 cover files, versions and remaining work.'),PageBreak()]
parts=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(d['title'])+'</title><style>body{font:17px/1.65 system-ui,sans-serif;max-width:900px;margin:40px auto;padding:0 24px;color:#202b35}h1,h2,h3{line-height:1.25;color:#000}section{margin:55px 0}pre{background:#f2f4f5;padding:16px;white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.7 monospace}table{border-collapse:collapse;width:100%;font-size:14px}td,th{border:1px solid #ddd;padding:10px;text-align:left}th{background:#eaf0f3}a{color:#176e55}.toc{columns:2;font-size:14px}@media print{section{break-before:page}body{font-size:11pt}pre{font-size:9pt}}@media(max-width:600px){.toc{columns:1}}</style><body><h1>'+esc(d['title'])+'</h1><p>'+esc(d['subtitle'])+'</p><p>'+esc(d['date'])+'</p><p>'+esc(d['intro'])+'</p><p><strong>Commands:</strong> copy full command lines from this HTML edition. In the PDF long lines may wrap visually.</p><nav class="toc">']
for i,s in enumerate(d['sections']):parts.append('<p><a href="#section'+str(i)+'">'+esc(s['title'])+'</a></p>')
parts.append('</nav>')
for i,s in enumerate(d['sections']):
 story.append(para(s['title'],'Heading1'));story.append(Spacer(1,8));parts.append('<section id="section'+str(i)+'"><h2>'+esc(s['title'])+'</h2>')
 for b in s['blocks']:
  t=b['type']
  if t=='p':story.append(para(b['text']));parts.append('<p>'+esc(b['text'])+'</p>')
  elif t=='sub':story.append(para(b['text'],'Heading2'));parts.append('<h3>'+esc(b['text'])+'</h3>')
  elif t=='code':story.append(Paragraph(esc(b['text']).replace('\n','<br/>'),styles['CodeGuide']));parts.append('<pre>'+esc(b['text'])+'</pre>')
  elif t=='bullets':
   parts.append('<ul>')
   for x in b['items']:story.append(para('- '+x));parts.append('<li>'+esc(x)+'</li>')
   parts.append('</ul>')
  elif t=='qa':story.append(para(b['q'],'Heading2'));story.append(para(b['a']));parts.append('<h3>'+esc(b['q'])+'</h3><p>'+esc(b['a'])+'</p>')
  elif t=='table':
   rows=[b['headers']]+b['rows'];cols=len(b['headers']);widths=([145,338] if cols==2 else [125,135,223])
   tab=Table([[para(str(c),'CellGuide') for c in r] for r in rows],colWidths=widths,repeatRows=1,hAlign='LEFT')
   tab.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eaf0f3')),('GRID',(0,0),(-1,-1),.5,colors.HexColor('#d9d9d9')),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
   story.extend([tab,Spacer(1,12)]);parts.append('<table><thead><tr>'+''.join('<th>'+esc(c)+'</th>' for c in b['headers'])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(str(c))+'</td>' for c in r)+'</tr>' for r in b['rows'])+'</tbody></table>')
 parts.append('</section>')
 if i<len(d['sections'])-1:story.append(PageBreak())
parts.append('</body></html>')
(ROOT/'docs/Video-QC-Learning-Guide.html').write_text(''.join(parts),encoding='utf-8')
def footer(canvas,doc):
 canvas.saveState();canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#67747b'));canvas.drawString(56,30,'Video QC learning guide | 14 October 2026');canvas.drawRightString(539,30,str(doc.page));canvas.restoreState()
pdf=ROOT/'docs/Video-QC-Learning-Guide.pdf'
SimpleDocTemplate(str(pdf),pagesize=(595.28,841.89),rightMargin=56,leftMargin=56,topMargin=48,bottomMargin=48,title=d['title'],author='Video QC project guide for Haroon').build(story,onFirstPage=footer,onLaterPages=footer)
import pypdfium2 as pdfium
from PIL import Image,ImageOps,ImageDraw
out=ROOT/'.cache/learning-guide-qa';out.mkdir(parents=True,exist_ok=True)
doc=pdfium.PdfDocument(str(pdf));thumbs=[]
for n in range(len(doc)):
 image=doc[n].render(scale=1).to_pil().convert('RGB');image.save(out/f'page-{n+1}.png')
 image.thumbnail((238,337));tile=Image.new('RGB',(258,367),'white');tile.paste(image,(10,10));ImageDraw.Draw(tile).text((10,349),str(n+1),fill='black');thumbs.append(tile)
for start in range(0,len(thumbs),12):
 batch=thumbs[start:start+12];sheet=Image.new('RGB',(258*4,367*3),'#d8dcdf')
 for j,t in enumerate(batch):sheet.paste(t,((j%4)*258,(j//4)*367))
 sheet.save(out/f'contact-{start//12+1}.jpg')
print(f'Created PDF and HTML; {len(doc)} pages; {len(d["sections"])} sections')
