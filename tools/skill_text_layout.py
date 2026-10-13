"""Skill-description paragraph formatting; preserve all non-whitespace text."""
import re
ATTRIBUTES={244:'智力',246:'智力',248:'敏捷',250:'智慧',252:'魅力',254:'智力',256:'智力',258:'智慧'}
BREAKS={244:['本技能等级'],246:['尝试拆除地雷','这项技能未经训练'],248:['处于“匿踪”模式中的角色','没有迷彩装置的话','这项技能未经训练'],250:['“洞察”技能总是激活的'],252:['当出现','选择这个选项后'],254:['本技能每总计','当队伍中的机器人'],256:['安保刺探器可','没有在这项技能'],258:['高级医疗包']}
def compact(text):return re.sub(r'\s+','',text)
def format_skill(ref,text):
    header='相关属性：'+ATTRIBUTES[ref]
    if not text.startswith(header):raise ValueError('Unexpected skill attribute header')
    body=text[len(header):].strip()
    # These eight descriptions contain Chinese prose and numeric rules, not
    # English multiword tokens. Refuse to remove an English word boundary.
    if re.search(r'[A-Za-z]',body):raise ValueError('Review English words before formatting')
    body=re.sub(r'[ \t]+','',body)
    for marker in BREAKS[ref]:
        if body.count(marker)!=1:raise ValueError('Skill paragraph marker changed: '+marker)
        body=body.replace(marker,'\n\n'+marker)
    result=header+'\n\n'+re.sub(r'\n{3,}','\n\n',body).lstrip('\n')
    assert compact(text)==compact(result)
    assert re.findall(r'[+-]?\d+',text)==re.findall(r'[+-]?\d+',result)
    return result
