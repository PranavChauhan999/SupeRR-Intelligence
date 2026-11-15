const reply = (value,status=200,headers={}) => new Response(JSON.stringify(value),{status,headers:{"Content-Type":"application/json; charset=utf-8","X-Content-Type-Options":"nosniff",...headers}});
export function serve(request,snapshot,html,splits) {
  const url=new URL(request.url), path=url.pathname;
  if(request.method!=="GET") return reply({error:"Use GET"},405,{Allow:"GET"});
  if(path==="/") return new Response(html,{headers:{"Content-Type":"text/html; charset=utf-8","X-Content-Type-Options":"nosniff"}});
  if(path==="/api/snapshot") return reply(snapshot);
  if(path==="/api/methodology") return reply({freeze:snapshot.freeze,config:snapshot.config,audit:snapshot.audit,validation:snapshot.validation});
  if(path==="/api/health") return reply({status:"ok",freeze:snapshot.freeze});
  const role=url.searchParams.get("role");
  if(role!==null && !["bat","bowl"].includes(role)) return reply({error:"role must be bat or bowl"},400);
  const pool=snapshot.players.filter(p=>!role||p.role===role);
  if(path==="/api/players") {
    const q=(url.searchParams.get("q")||"").toLowerCase();
    return reply({freeze:snapshot.freeze,players:pool.filter(p=>p.name.toLowerCase().includes(q))});
  }
  if(path.startsWith("/api/splits/")) {
    const key=path.slice("/api/splits/".length);
    if(!splits||splits.freeze!==snapshot.freeze) return reply({error:"Splits unavailable for this snapshot"},503);
    return Object.hasOwn(splits.by_player,key)?reply({freeze:snapshot.freeze,rows:splits.by_player[key]}):reply({error:"Player not found"},404);
  }
  if(/^\/api\/players\/(bat|bowl)\/\d+$/.test(path)) {
    const [, , ,r,id]=path.split("/");
    const player=pool.find(p=>p.role===r&&String(p.id)===id);
    return player?reply({freeze:snapshot.freeze,player}):reply({error:"Player not found"},404);
  }
  const ranks=pool.filter(p=>p.rank&&p.rank<=10).sort((a,b)=>a.role.localeCompare(b.role)||a.rank-b.rank);
  if(path==="/api/rankings") return reply({freeze:snapshot.freeze,players:ranks});
  if(path==="/api/export.csv") {
    const header=["role","rank","name","id","score","balls","normal_balls","matches","runs","wickets","ipl_balls","top10","strict","loose"];
    const csv=[header.join(","),...ranks.map(row=>header.map(k=>'"'+String(row[k]??"").replaceAll('"','""')+'"').join(","))].join("\r\n")+"\r\n";
    return new Response(csv,{headers:{"Content-Type":"text/csv; charset=utf-8","Content-Disposition":'attachment; filename="SupeRR-rankings.csv"'}});
  }
  return reply({error:"Route not found"},404);
}
