"""Bounded, declarative chart data. Never accept executable chart options."""
import math
TYPES={'column','bar','stackedColumn','stackedBar','line','area','stackedArea','pie','doughnut','scatter','bubble','radar','histogram','boxplot','stock','waterfall','funnel','treemap','sunburst','heatmap','combo','gauge'}
def validate(c):
    if not isinstance(c,dict) or c.get('type') not in TYPES: raise ValueError('Choose a supported chart type.')
    for key in ['title','subtitle','xTitle','yTitle']:
        if not isinstance(c.get(key),str) or len(c[key])>200: raise ValueError('Chart text must be at most 200 characters.')
    if c.get('font') not in ['Times New Roman','Arial','Georgia','Verdana']: raise ValueError('Invalid chart font.')
    if type(c.get('fontSize')) is not int or not 10<=c['fontSize']<=32: raise ValueError('Chart font size must be 10–32.')
    for k in ['legend','grid','labels','smooth']:
        if type(c.get(k)) is not bool: raise ValueError('Invalid chart setting.')
    if c.get('legendPosition') not in ['top','bottom']: raise ValueError('Invalid legend position.')
    import re
    for k in ['background','textColor']:
        if not isinstance(c.get(k),str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',c[k]): raise ValueError('Invalid chart color.')
    colors=c.get('colors')
    if not isinstance(colors,list) or not 1<=len(colors)<=50 or any(not isinstance(v,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',v) for v in colors): raise ValueError('Invalid chart colors.')
    headers=c.get('headers'); rows=c.get('rows')
    if not isinstance(headers,list) or not 2<=len(headers)<=13 or any(not isinstance(x,str) or not x.strip() or len(x)>100 for x in headers): raise ValueError('Use a category column and 1–12 named series.')
    if not isinstance(rows,list) or not 1<=len(rows)<=200: raise ValueError('Use 1–200 chart rows.')
    for row in rows:
        if not isinstance(row,list) or len(row)!=len(headers) or not isinstance(row[0],str) or len(row[0])>100: raise ValueError('Invalid chart row.')
        if any(type(x) not in (int,float) or not math.isfinite(x) or abs(x)>1e12 for x in row[1:]): raise ValueError('Chart values must be finite numbers between -1 trillion and 1 trillion.')
