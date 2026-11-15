import http from 'node:http';
import fs from 'node:fs';
import {serve} from './api.mjs';
import {documents,fileResponse} from './documents.mjs';
const file=(name)=>new URL(name,import.meta.url);
const snapshot=JSON.parse(fs.readFileSync(file('data/snapshot.json')));
const splits=JSON.parse(fs.readFileSync(file('data/splits.json')));
const arg=(key)=>{const i=process.argv.indexOf(key);return i>=0?process.argv[i+1]:null;};
const port=Number(arg('--port')||process.env.PORT||3000);
http.createServer(async(req,res)=>{
  try{
    const request=new Request(new URL(req.url,'http://localhost'),{method:req.method});
    const path=new URL(request.url).pathname;
    const result=req.method==='GET'&&path==='/assets/cover.webp'
      ?new Response(fs.readFileSync(file('assets/cover.webp')),{headers:{'Content-Type':'image/webp'}})
      :req.method==='GET'&&Object.hasOwn(documents,path)
      ?fileResponse(path,fs.readFileSync(file('files/'+documents[path][0])))
      :serve(request,snapshot,path==='/'?fs.readFileSync(file('ui.html'),'utf8'):'',splits);
    res.writeHead(result.status,Object.fromEntries(result.headers));res.end(Buffer.from(await result.arrayBuffer()));
  }catch{res.writeHead(503,{'Content-Type':'text/plain'});res.end('This resource is temporarily unavailable.');}
}).listen(port,arg('--host')||'0.0.0.0',()=>console.log('SupeRR listening on '+port));
