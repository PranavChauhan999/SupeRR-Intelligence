export const documents={
  "/files/brief.pptx":["SupeRR-Auction-Brief.pptx","application/vnd.openxmlformats-officedocument.presentationml.presentation"],
  "/files/report.pdf":["SupeRR-Methodology.pdf","application/pdf"],
  "/files/unstop.txt":["SupeRR-Unstop.txt","text/plain; charset=utf-8"]
};
export function fileResponse(path,bytes){
  const [name,type]=documents[path];
  return new Response(bytes,{headers:{"Content-Type":type,"Content-Disposition":'attachment; filename="'+name+'"',"X-Content-Type-Options":"nosniff"}});
}
