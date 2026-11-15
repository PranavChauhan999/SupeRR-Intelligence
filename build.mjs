import fs from 'node:fs';
import {documents} from './documents.mjs';
const splits=JSON.parse(fs.readFileSync('data/splits.json'));
const snapshot=JSON.parse(fs.readFileSync('data/snapshot.json'));
const html=fs.readFileSync('ui.html','utf8');
const exports=Object.fromEntries(Object.entries(documents).map(([path,[name,type]])=>[path,{name,type,base64:fs.readFileSync('files/'+name).toString('base64')}]));
exports["/assets/cover.webp"]={name:"cover.webp",type:"image/webp",base64:fs.readFileSync("assets/cover.webp").toString("base64")};
const source=fs.readFileSync('api.mjs','utf8').replace('export function serve','function serve');
const worker=source+'\nconst snapshot='+JSON.stringify(snapshot)+';\nconst splits='+JSON.stringify(splits)+';\nconst html='+JSON.stringify(html)+';\nconst resources='+JSON.stringify(exports)+`;
export default {fetch(request){
 const path=new URL(request.url).pathname;
 const item=Object.hasOwn(resources,path)&&resources[path];
 if(request.method==="GET"&&item){const bytes=Uint8Array.from(atob(item.base64),c=>c.charCodeAt(0));return new Response(bytes,{headers:{"Content-Type":item.type,"Content-Disposition":(path.startsWith('/assets/')?'inline':'attachment')+'; filename="'+item.name+'"'}});}
 return serve(request,snapshot,html,splits);
}};`;
fs.mkdirSync('dist/server',{recursive:true});
fs.writeFileSync('dist/server/index.js',worker);
