import type { ModelProtocol } from '../../../shared/contracts';
export const modelPresets: Array<{name:string; protocol:ModelProtocol; endpoint:string; local?:boolean; note?:string}> = [
 {name:'DeepSeek',protocol:'openai_compatible',endpoint:'https://api.deepseek.com'},
 {name:'通义千问（百炼）',protocol:'openai_compatible',endpoint:'https://dashscope.aliyuncs.com/compatible-mode/v1',note:'北京地域兼容地址；也可填写业务空间专属地址，须与密钥地域一致。'},
 {name:'智谱 GLM',protocol:'openai_compatible',endpoint:'https://open.bigmodel.cn/api/paas/v4'},
 {name:'豆包（火山方舟）',protocol:'openai_compatible',endpoint:'https://ark.cn-beijing.volces.com/api/v3',note:'填写控制台可调用的模型 ID 或推理接入点 ID。'},
 {name:'Kimi',protocol:'openai_compatible',endpoint:'https://api.moonshot.cn/v1'},
 {name:'硅基流动',protocol:'openai_compatible',endpoint:'https://api.siliconflow.cn/v1'},
 {name:'OpenAI',protocol:'openai_compatible',endpoint:'https://api.openai.com/v1'},
 {name:'Claude',protocol:'anthropic',endpoint:'https://api.anthropic.com/v1'},
 {name:'Gemini',protocol:'gemini',endpoint:'https://generativelanguage.googleapis.com/v1beta'},
 {name:'Ollama（本机）',protocol:'openai_compatible',endpoint:'http://localhost:11434/v1',local:true},
 {name:'LM Studio（本机）',protocol:'openai_compatible',endpoint:'http://localhost:1234/v1',local:true},
 {name:'自定义',protocol:'openai_compatible',endpoint:''},
];
export const protocolNames = {openai_compatible:'OpenAI 兼容',anthropic:'Anthropic 原生',gemini:'Gemini 原生'};
