"""Apply individually reviewed dialogue revisions, with exact source/before guards."""
import collections,hashlib,json
from pathlib import Path
from name_terminology import PROTECTED
def digest(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()
def apply_approved(row,edit):
    if row['id']!=edit['id'] or row['source_sha256']!=edit['source_sha256']:
        raise ValueError('Dialogue ID/source hash mismatch')
    if row['zh']==edit['after']:return dict(row),False
    if digest(row['zh'])!=edit['before_sha256'] or row['zh']!=edit['before']:
        raise ValueError('Translation changed since contextual review; do not overwrite it')
    if PROTECTED.findall(edit['before'])!=PROTECTED.findall(edit['after']):
        raise ValueError('Protected variables or authoring notes changed')
    revised=dict(row,zh=edit['after'],status='reviewed')
    return revised,True
def check_known_dialogue_issues(data,approved):
    indexed={r['id']:r for rows in data.values() for r in rows}
    for edit in approved:
        row=indexed[edit['id']]
        assert row['source_sha256']==edit['source_sha256'],edit['id']
        assert row['zh']!=edit['before'],(edit['id'],'Known contextual dialogue issue reintroduced')
