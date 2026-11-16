import test from 'node:test';
import assert from 'node:assert/strict';
import {modernRoute} from './src/router.js';
import {open} from './src/tickets.js';

test('production catalog delegates to Python after quota and preserves results',async()=>{
    const calls=[];
    const response=await modernRoute(new Request('https://example.test/api/v3/anime?page=2'),{
        CONTENT_ON_RAILWAY:true,
        ledger:async data=>{calls.push(data.action);return {status:200};},
        engine:async(action,params)=>{
            calls.push(action);assert.equal(params.path,'/api/v3/anime');assert.equal(params.query.page,'2');
            return {kind:'results',data:{items:[],page:2,total:0}};
        }
    });
    assert.deepEqual(calls,['consume','catalog-query']);
    assert.equal(response.status,200);
    assert.deepEqual((await response.json()).results,{items:[],page:2,total:0});
});

test('Python content cannot bypass the edge quota gate',async()=>{
    const response=await modernRoute(new Request('https://example.test/api/v3/anime'),{
        CONTENT_ON_RAILWAY:true,
        ledger:async()=>({status:429,message:'Daily limit exceeded'}),
        engine:async()=>assert.fail('No content request is allowed after quota rejection')
    });
    assert.equal(response.status,429);
});

test('trailer metadata keeps its shape and playback goes through the authenticated relay',async()=>{
    const response=await modernRoute(new Request('https://example.test/api/v3/info/12345?apikey=fixture'),{
        ADMIN_SECRET:'fixture',CONTENT_ON_RAILWAY:true,
        ledger:async()=>({status:200}),
        engine:async()=>({kind:'results',data:{title:'Fixture',trailer:{videoAddress:{url:'https://cdn.aoneroom.com/trailer.mp4',duration:90}}}})
    });
    const data=await response.json();
    const trailer=data.results.trailer.videoAddress;
    const url=new URL(trailer.url);
    assert.equal(url.origin,'https://example.test');
    assert.equal(url.pathname,'/api/v3/stream');
    assert.equal(trailer.duration,90);
    assert.equal(open(url.searchParams.get('ticket'),'fixture').url,'https://cdn.aoneroom.com/trailer.mp4');
});
