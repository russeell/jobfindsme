import type {Model} from "@earendil-works/pi-ai";
import type {ModelConnection} from "../../shared/contracts.js";
export function modelFor(connection:ModelConnection):Model<any>{const api=connection.protocol==="anthropic"?"anthropic-messages":connection.protocol==="gemini"?"google-generative-ai":"openai-completions";return {id:connection.model_id,name:connection.model_id,api,provider:connection.provider,baseUrl:connection.endpoint,reasoning:false,input:["text","image"],cost:{input:0,output:0,cacheRead:0,cacheWrite:0},contextWindow:32768,maxTokens:2048};}
