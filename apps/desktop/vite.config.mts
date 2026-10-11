import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import {readFileSync,readdirSync} from "node:fs";
import {fileURLToPath} from "node:url";

// Bundle the official PDF.js resources and their license files; never fetch a CDN.
const pdfResources=new Map<string,Buffer>();
for(const directory of ["cmaps","standard_fonts","wasm"]){
  const root=new URL(`./node_modules/pdfjs-dist/${directory}/`,import.meta.url);
  for(const name of readdirSync(root))pdfResources.set(`pdfjs/${directory}/${name}`,readFileSync(fileURLToPath(new URL(name,root))));
}
const pdfAssets={name:"local-pdf-assets",
  generateBundle(){for(const [fileName,source] of pdfResources)this.emitFile({type:"asset",fileName,source});},
  configureServer(server){server.middlewares.use((request,response,next)=>{
    const name=request.url?.split('?')[0]?.replace(/^\//,'');
    const data=name?pdfResources.get(name):undefined;
    if(!data)return next();
    response.setHeader('Content-Type',name!.endsWith('.js')?'text/javascript':name!.endsWith('.wasm')?'application/wasm':'application/octet-stream');
    response.end(data);
  });}
} satisfies import("vite").Plugin;

export default defineConfig({
  plugins: [react(),pdfAssets],
  root: "renderer",
  publicDir: "../public",
  base: "./",
  build: { outDir: "../dist", emptyOutDir: true },
});
