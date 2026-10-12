"""Recover bilingual records locally; never modify the public translation tables."""
import argparse,json
from pathlib import Path
from public_project import translations,english_sources

def main(output):
    assert not output.exists(),'Use a new output directory'
    data=translations();_,sources,_=english_sources(data);output.mkdir(parents=True)
    for profile,rows in data.items():
        with (output/(profile+'.jsonl')).open('w',encoding='utf-8',newline='\n') as f:
            for row in rows:f.write(json.dumps(dict(row,source=sources[row['id']]),ensure_ascii=False)+'\n')
    print('Recovered exact sources for '+str(sum(len(r) for r in data.values()))+' records.')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
