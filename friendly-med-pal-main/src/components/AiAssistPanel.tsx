import { useState, useRef, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Loader2, Image as ImageIcon, Sparkles, Repeat2 } from 'lucide-react';
import { api } from '@/api/client';

type Role = 'user' | 'assistant';
interface ChatMessage { role: Role; content: string; }
interface ImageGen { image: string; prompt: string; ai: boolean; width: number; height: number; style: string; }

export default function AiAssistPanel(){
  // Chat state
  const [history,setHistory] = useState<ChatMessage[]>([ {role:'assistant', content: 'Hi! Ask me about patients, deliveries or generate an image.'} ]);
  const [chatInput,setChatInput] = useState('');
  const [chatLoading,setChatLoading] = useState(false);
  const endRef = useRef<HTMLDivElement|null>(null);

  // Image gen state
  const [imgPrompt,setImgPrompt]=useState('Colorful abstract for medication adherence');
  const [imgStyle,setImgStyle]=useState('cool');
  const [imgSize,setImgSize]=useState<'sm'|'md'|'lg'>('md');
  const [imgLoading,setImgLoading]=useState(false);
  const [images,setImages]=useState<ImageGen[]>([]);
  const [rewriteMode,setRewriteMode]=useState<'simplify'|'bulletize'>('simplify');
  const [rewriteInput,setRewriteInput]=useState('');
  const [rewriteOutput,setRewriteOutput]=useState('');
  const [rewriteLoading,setRewriteLoading]=useState(false);

  useEffect(()=>{ endRef.current?.scrollIntoView({behavior:'smooth'}); }, [history]);

  async function sendChat(){
    if(!chatInput.trim()) return;
  const newHist: ChatMessage[] =[...history,{role:'user',content:chatInput.trim()}];
    setHistory(newHist);
    setChatInput('');
    setChatLoading(true);
    try {
  const res = await api<{reply:string; history:{role:string;content:string;}[]}>('/ai/chat',{method:'POST', body: JSON.stringify({history:newHist})});
  // Coerce roles to typed union
  const coerced: ChatMessage[] = res.history.map(m=> ({role: m.role === 'assistant' ? 'assistant':'user', content: m.content}));
  setHistory(coerced);
    } catch(e:any){
      setHistory(h=>[...h,{role:'assistant', content: 'Error: '+(e?.message||e)}]);
    } finally { setChatLoading(false); }
  }

  async function generateImage(){
    if(!imgPrompt.trim()) return;
    setImgLoading(true);
    try {
      let dims: [number,number];
      switch(imgSize){
        case 'sm': dims=[256,256]; break;
        case 'lg': dims=[768,768]; break;
        default: dims=[512,512];
      }
      const res = await api<ImageGen>('/ai/image',{method:'POST', body: JSON.stringify({prompt: imgPrompt, width:dims[0], height:dims[1], style: imgStyle})}, 60000);
      setImages(imgs=> [res, ...imgs].slice(0,12));
    } catch(e:any){
      setImages(imgs=> [{image:'', prompt: 'Error: '+(e?.message||e), ai:false, width:0, height:0, style:''}, ...imgs]);
    } finally { setImgLoading(false); }
  }

  async function doRewrite(){
    if(!rewriteInput.trim()) return;
    setRewriteLoading(true);
    try {
      const res = await api<{rewritten:string; mode:string}>('/ai/rewrite',{method:'POST', body: JSON.stringify({text: rewriteInput, mode: rewriteMode})});
      setRewriteOutput(res.rewritten);
    } catch(e:any){ setRewriteOutput('Error: '+(e?.message||e)); }
    finally { setRewriteLoading(false); }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>AI Assistant</CardTitle>
          <CardDescription>Chat, generate images, and rewrite text.</CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="chat" className="w-full">
            <TabsList className="grid grid-cols-3 w-full">
              <TabsTrigger value="chat">Chat</TabsTrigger>
              <TabsTrigger value="image">Images</TabsTrigger>
              <TabsTrigger value="rewrite">Rewrite</TabsTrigger>
            </TabsList>
            <TabsContent value="chat" className="mt-4 space-y-3">
              <div className="h-72 border rounded-md p-3 overflow-auto bg-muted/30 text-sm space-y-3">
                {history.map((m,i)=>(
                  <div key={i+':' + m.role + ':' + (m.content.slice(0,16))} className={m.role==='user'? 'text-foreground' : 'text-primary'}>
                    <span className="font-medium mr-1">{m.role==='user'? 'You:' : 'AI:'}</span>
                    <span className="whitespace-pre-wrap break-words">{m.content}</span>
                  </div>
                ))}
                {chatLoading && <div className="flex items-center gap-2 text-muted-foreground text-xs"><Loader2 className="w-3 h-3 animate-spin"/>Thinking...</div>}
                <div ref={endRef}/>
              </div>
              <div className="flex gap-2">
                <Textarea value={chatInput} onChange={e=> setChatInput(e.target.value)} placeholder="Ask something..." className="min-h-[60px]"/>
                <Button onClick={sendChat} disabled={chatLoading || !chatInput.trim()} className="self-end">Send</Button>
              </div>
            </TabsContent>
            <TabsContent value="image" className="mt-4 space-y-4">
              <div className="flex flex-col gap-3 md:flex-row">
                <Input value={imgPrompt} onChange={e=> setImgPrompt(e.target.value)} placeholder="Prompt" className="flex-1"/>
                <select aria-label="Image style" value={imgStyle} onChange={e=> setImgStyle(e.target.value)} className="border rounded-md px-2 py-2 bg-background text-sm">
                  <option value="cool">Cool</option>
                  <option value="warm">Warm</option>
                  <option value="mono">Mono</option>
                </select>
                <select aria-label="Image size" value={imgSize} onChange={e=> setImgSize(e.target.value as any)} className="border rounded-md px-2 py-2 bg-background text-sm">
                  <option value="sm">256</option>
                  <option value="md">512</option>
                  <option value="lg">768</option>
                </select>
                <Button onClick={generateImage} disabled={imgLoading}>
                  {imgLoading? <Loader2 className="w-4 h-4 animate-spin"/> : <ImageIcon className="w-4 h-4"/>}
                  <span className="ml-2">Generate</span>
                </Button>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                {images.map((im,i)=>(
                  <div key={(im.image||'err')+'#'+i} className="relative group border rounded-md overflow-hidden bg-muted/20">
                    {im.image? <img src={im.image} alt={im.prompt} className="w-full h-full object-cover aspect-square"/> : <div className="p-2 text-xs text-destructive">{im.prompt}</div>}
                    <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition flex items-end p-2">
                      <p className="text-[10px] leading-tight text-white/90 line-clamp-4">
                        {im.prompt}
                      </p>
                    </div>
                  </div>
                ))}
                {imgLoading && <div className="flex items-center justify-center border rounded-md h-32 animate-pulse text-xs text-muted-foreground">Generating...</div>}
              </div>
            </TabsContent>
            <TabsContent value="rewrite" className="mt-4 space-y-4">
              <div className="flex gap-2 flex-wrap items-center">
                <select aria-label="Rewrite mode" value={rewriteMode} onChange={e=> setRewriteMode(e.target.value as any)} className="border rounded-md px-2 py-2 bg-background text-sm">
                  <option value="simplify">Simplify</option>
                  <option value="bulletize">Bulletize</option>
                </select>
                <Button onClick={doRewrite} disabled={rewriteLoading || !rewriteInput.trim()}>
                  {rewriteLoading? <Loader2 className="w-4 h-4 animate-spin"/> : <Repeat2 className="w-4 h-4"/>}
                  <span className="ml-2">Rewrite</span>
                </Button>
              </div>
              <Textarea value={rewriteInput} onChange={e=> setRewriteInput(e.target.value)} placeholder="Paste text to transform..." className="min-h-[120px]"/>
              {rewriteLoading && <div className="text-xs text-muted-foreground flex items-center gap-2"><Loader2 className="w-3 h-3 animate-spin"/>Processing...</div>}
              {rewriteOutput && (
                <div className="border rounded-md p-3 bg-muted/30 text-sm whitespace-pre-wrap break-words">
                  {rewriteOutput}
                </div>
              )}
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
      <Card className="bg-gradient-to-br from-primary/5 to-primary/10 border-primary/20">
        <CardContent className="p-4 text-xs text-muted-foreground flex gap-2 items-start">
          <Sparkles className="w-4 h-4 text-primary"/>
          <p>Images fall back to a procedural generator if the remote model isn\'t available. Provide a valid API key in the backend environment to enable real image generation.</p>
        </CardContent>
      </Card>
    </div>
  );
}
