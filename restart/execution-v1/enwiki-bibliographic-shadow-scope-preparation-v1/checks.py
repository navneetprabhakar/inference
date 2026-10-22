from pathlib import Path
import sys,json
B=Path(__file__).resolve().parent.parent;sys.path[:0]=[str(Path(__file__).resolve().parent),str(B/'tool-dependencies/mwparserfromhell-0.7.2'),str(B/'enwiki-short-footnote-preparation-v2'),str(B/'enwiki-generic-AST-policy-preparation-v4')]
import mwparserfromhell as parser,short_core as short,policy_core as literal,shadow
cases=[]
def run(text,expected):
 n=parser.parse(text).nodes[0];c=shadow.constraint(n,'nonliteral_binding_or_qualifier_AST',short,literal);assert c['kind']==expected;(cases.append({'text':text,'constraint':c}));return c
c=run('{{cite web|author=[[Some Person]]|date=26 December 2020|title=T}}','ANY_AUTHOR_BASE_YEAR');assert shadow.shadows(c,('Unrelated Author','2020')) and shadow.shadows(c,('Different','2020a')) and not shadow.shadows(c,('Shaw','2012'))
run('{{cite web|author=[[Some Person|Display]]|year=2020|date=2020-12-11}}','ANY_AUTHOR_BASE_YEAR')
for text in ['{{cite web|author=[[A]]|date=2020-02-30}}','{{cite web|author=[[A]]|date={{unknown}}}}','{{cite web|author=[[A]]|date=2020|ref={{unknown}}}}','{{cite web|author=[[A]]|date=2020|year=2019}}','{{cite web|author=[[A]]}}','{{cite web|author=[[A]]|date=2020|author=other}}','{{cite web|author=[[A]]|date=2020|last=Other}}','{{cite web|author=[[{{unknown}}]]|date=2020}}','{{cite web|author=[[A|{{unknown}}]]|date=2020}}','{{cite web|author={{unknown}}|date=2020}}','{{cite web|author=[[A]]|date=2020|title=<ref>Hidden</ref>}}']:
 c=run(text,'GLOBAL_UNBOUND');assert shadow.shadows(c,('Shaw','2012'))
print(json.dumps({'status':'PASS_SYNTHETIC_SHADOW_PROPOSAL_ONLY_NO_SOURCE_APPLICATION','controls':len(cases),'cases':cases},indent=2))
