import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';import {serve} from './api.mjs';
const data=JSON.parse(fs.readFileSync(new URL('./data/snapshot.json',import.meta.url)));
const splits=JSON.parse(fs.readFileSync(new URL('./data/splits.json',import.meta.url)));
const call=(path,method='GET')=>serve(new Request('http://localhost'+path,{method}),data,'<html></html>',splits);
for(const path of ['/','/api/snapshot','/api/health','/api/methodology','/api/players','/api/rankings','/api/export.csv']) test(path,()=>assert.equal(call(path).status,200));
for(const role of ['bat','bowl'])test('exact order '+role,async()=>{const {players}=await call('/api/rankings?role='+role).json();assert.deepEqual(players.map(p=>p.rank),[1,2,3,4,5,6,7,8,9,10]);for(const p of players){const detail=await call('/api/players/'+role+'/'+p.id).json();assert.deepEqual(detail.player,p);assert.ok((await call('/api/players?role='+role+'&q='+encodeURIComponent(p.name)).json()).players.some(x=>x.id===p.id));}assert.equal((await call('/api/export.csv?role='+role).text()).trim().split(/\r?\n/).length,11)});
test('errors',()=>{assert.equal(call('/api/rankings?role=invalid').status,400);assert.equal(call('/bad').status,404);assert.equal(call('/api/players/bat/000').status,404);assert.equal(call('/api/health','POST').status,405)});

test('season and league accounting for every player and role',async()=>{
  for(const p of data.players){
    const res=await call('/api/splits/'+p.role+'/'+p.id).json();assert.equal(res.freeze,data.freeze);
    const pressure=res.rows.filter(row=>row.pressure);
    for(const key of ['balls','runs','wickets']) assert.equal(pressure.reduce((v,row)=>v+row[key],0),p[key]);
    assert.equal(pressure.filter(row=>row.league==='IPL').reduce((v,row)=>v+row.balls,0),p.ipl_balls);
  }
});
