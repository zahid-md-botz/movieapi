import { Readable } from 'node:stream';
import { MovieBox } from './moviebox.js';
import { modernRoute,json,secretEqual } from './router.js';
import { open } from './tickets.js';
import { fetchMedia } from './media-relay.js';
import { createOutboundFetch } from './outbound.js';

const outbound=createOutboundFetch();
const engine=new MovieBox(outbound);
const media=(url,headers,range,method,ifRange)=>fetchMedia(url,headers,range,method,outbound,ifRange);
const callEngine=(action,params)=>engine.call(action,params);
async function send(response,res) {
    res.status(response.status);
    for(const [k,v] of response.headers) res.setHeader(k,v);
    if(!response.body) return res.end();
    const stream=Readable.fromWeb(response.body);
    res.on('close',()=>stream.destroy());
    stream.on('error',()=>res.destroy());
    stream.pipe(res);
}
export function installModern(app) {
    app.use(async(req,res,next)=>{
        try {
            if(['/internal/moviebox','/internal/moviebox-media'].includes(req.path)) {
                if(!secretEqual(req.headers['x-relay-secret'],process.env.ADMIN_SECRET))
                    return send(json({message:'Unauthorized'},401),res);
                if(req.method!=='POST') return send(json({message:'Use POST'},405),res);
                if(req.path==='/internal/moviebox') {
                    const results=await callEngine(req.body.action,req.body.params||{});
                    return send(json({results}),res);
                }
                const data=open(req.body.ticket,process.env.ADMIN_SECRET);
                return send(await media(data.url,data.headers,req.headers.range,req.body.method==='HEAD'?'HEAD':'GET',req.headers['if-range']),res);
            }
            if(req.path==='/internal/edge-media') {
                if(!secretEqual(req.headers['x-edge-secret'],process.env.EDGE_SHARED_SECRET))
                    return send(json({message:'Unauthorized'},401),res);
                if(req.method!=='POST') return send(json({message:'Use POST'},405),res);
                const token=String(req.body?.token||'');
                if(!/^[A-Za-z0-9_-]{24}$/.test(token)) return send(json({message:'Invalid playback token'},400),res);
                const {localLedger}=await import('./local-ledger.js');
                const result=localLedger.dispatch({action:'playback-get',token});
                if(result.status!==200) return send(json({message:result.message},result.status),res);
                return send(json({data:result.data}),res);
            }
            if(process.env.NODE_ENV==='production' && (
                req.path.startsWith('/debug/') || req.path.startsWith('/try-') ||
                req.path.startsWith('/sample-') || req.path.startsWith('/internal/')
            )) return send(json({message:'Endpoint not available'},404),res);
            const protocol=req.headers['x-forwarded-proto']?.split(',')[0] || req.protocol;
            const url=`${protocol}://${req.get('host')}${req.originalUrl}`;
            const request=new Request(url,{method:req.method,headers:req.headers,
                ...(!['GET','HEAD'].includes(req.method)?{body:JSON.stringify(req.body||{})}:{})});
            const runtime={
                ADMIN_SECRET:process.env.ADMIN_SECRET,
                EDGE_SHARED_SECRET:process.env.EDGE_SHARED_SECRET,
                PUBLIC_BASE_URL:process.env.PUBLIC_BASE_URL,
                STORAGE_LABEL:'railway-volume-sqlite',
                ledger:async data=>{
                    try {
                        const {localLedger}=await import('./local-ledger.js');
                        return localLedger.dispatch(data);
                    } catch(e) {
                        console.error('[key-ledger] SQLite operation failed:', e.message);
                        return {status:e.status||503,code:e.code||'KEY_STORE_UNAVAILABLE',
                            message:e.status?e.message:'Persistent key storage is temporarily unavailable'};
                    }
                },
                engine:callEngine,
                media
            };
            const response=await modernRoute(request,runtime);
            if(response) return send(response,res);
            next();
        } catch(e) {return send(json({message:e.message},e.status||502),res);}
    });
}
