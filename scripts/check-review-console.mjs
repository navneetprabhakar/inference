// Creator: Navneet Prabhakar
// JavaScript unit simulation only. No browser, rendering, networking or real review.
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const [htmlPath,patchPath,reportPath]=process.argv.slice(2);
if(!reportPath)throw Error('Pass synthetic HTML, fresh patch path and report path');
const html=fs.readFileSync(htmlPath,'utf8'),script=html.split('<script>')[1].split('</script>')[0];
const encoded=script.match(/atob\('([A-Za-z0-9+/=]+)'\)/)[1];
const payload=JSON.parse(Buffer.from(encoded,'base64').toString('utf8'));
assert.deepEqual(Object.keys(payload.packet.source_reviews),['fixture']);
assert.equal(payload.packet.source_reviews.fixture.source_record.license_id,'fixture');
assert(Object.values(payload.packet.examples).every(v=>v.record.source==='fixture'));
class Element{
 constructor(tag,text=''){this.tag=tag;this.text=text;this.children=[];this.events={};this.value='';this.checked=false;this.disabled=false;this.files=[];}
 get textContent(){return this.text+this.children.map(v=>v.textContent).join('');}
 set textContent(v){this.text=String(v);this.children=[];}
 append(child){this.children.push(child);child.parent=this;}
 replaceChildren(){this.children=[];this.text='';}
 addEventListener(name,fn){(this.events[name]??=[]).push(fn);}
 async dispatch(name){for(const fn of this.events[name]??[])await fn({target:this});}
 click(){return this.dispatch('click');}
 remove(){this.parent.children=this.parent.children.filter(v=>v!==this);}
 set selected(v){if(v&&this.parent?.tag==='select')this.parent.value=this.value;}
}
const body=new Element('body'),ids={};
for(const [,id] of html.matchAll(/\bid="([^"]+)"/g)){ids[id]=new Element(id==='choose'?'select':'div');body.append(ids[id]);}
const document={body,createElement:t=>new Element(t),createTextNode:t=>new Element('text',t),getElementById:id=>ids[id]};
const blobs=[];
const context={document,TextDecoder,TextEncoder,Uint8Array,atob,structuredClone,Blob,
 URL:{createObjectURL:b=>{blobs.push(b);return 'blob:unit-simulation';},revokeObjectURL:()=>{}},setTimeout:()=>0};
vm.runInNewContext(script,context,{timeout:2000});
const walk=n=>[n,...n.children.flatMap(walk)];
function control(label,tag){const row=walk(body).find(v=>v.tag==='label'&&v.text===label);assert(row,label);const c=row.children.find(v=>v.tag===tag);assert(c,label);return c;}
async function select(label,value){const c=control(label,'select');c.value=JSON.stringify(value);await c.dispatch('change');}
async function text(label,value){const c=control(label,'textarea');c.value=value;await c.dispatch('input');}
assert.equal(ids.attest.checked,false);assert.match(ids.status.textContent,/Sources: 0 approved/);
await ids.export.click();const draft=JSON.parse(ids['patch-preview'].textContent);
assert.equal(draft.human_attestation,false);assert(Object.values(draft.examples).every(v=>v.approved===null));
const id=Object.keys(payload.packet.examples).find(k=>payload.packet.examples[k].record.split==='train');assert(id);
ids.choose.value=id;await ids.choose.dispatch('change');
await select('Source approval',true);await select('Terms reviewed',true);
const category=walk(body).find(v=>v.tag==='label'&&v.textContent.trim()==='sfw');assert(category);
const checkbox=category.children.find(v=>v.tag==='input');checkbox.checked=true;await checkbox.dispatch('change');
await text('Terms/category evidence note','Synthetic unit fixture decision only; not public-source review.');
for(const label of ['Example approval','English verified','Privacy verified','Quality verified'])await select(label,true);
await select('Content category','sfw');await select('Verified upstream partition','train');await text('Partition evidence','Synthetic fixture partition.');
ids.attest.checked=true;await ids.export.click();const approved=JSON.parse(ids['patch-preview'].textContent);
assert.equal(approved.human_attestation,true);assert.equal(Object.values(approved.examples).filter(v=>v.approved===true).length,1);
assert.equal(approved.examples[id].upstream_partition,'train');assert.equal(blobs.length,2);
assert.deepEqual(JSON.parse(await blobs[1].text()),approved);
// A stale import is refused and cannot replace the displayed decisions.
const stale=structuredClone(approved);stale.review_packet_sha256='0'.repeat(64);
ids.import.files=[{size:JSON.stringify(stale).length,text:async()=>JSON.stringify(stale)}];await ids.import.dispatch('change');
assert.match(ids.error.textContent,/Different packet/);
ids.import.files=[{size:JSON.stringify(approved).length,text:async()=>JSON.stringify(approved)}];await ids.import.dispatch('change');
assert.equal(ids.attest.checked,false);assert.match(ids.error.textContent,/Attestation remains unchecked/);
await ids.export.click();assert.equal(JSON.parse(ids['patch-preview'].textContent).human_attestation,false);
fs.writeFileSync(patchPath,JSON.stringify(approved,null,2)+'\n',{flag:'wx'});
const report={creator:'Navneet Prabhakar',dom_simulation_completed:true,browser_runtime_verified:false,visual_layout_verified:false,
 real_human_review:false,synthetic_only:true,fixture_examples:Object.keys(approved.examples).length,
 synthetic_approved_examples:1,draft_stays_unattested:true,stale_import_refused:true,import_resets_attestation:true,
 blob_content_matches_preview:true,network_calls:0,scope:'Unit-simulated DOM events and JSON Blob content; no real browser download or CSP enforcement proof'};
fs.writeFileSync(reportPath,JSON.stringify(report,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify(report));
