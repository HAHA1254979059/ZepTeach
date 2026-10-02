const fs = require('fs');
const path = require('path');
const {pathToFileURL} = require('url');
const {createHash} = require('crypto');
const {chromium} = require(process.argv[2]);
const config = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const assert = (ok, message) => {if (!ok) throw new Error(message);};
const cases = [
  {name:'pending',total:264,count:null,indices:[]},
  {name:'zero',total:264,count:0,indices:[]},
  {name:'positive-visible',total:264,count:1,indices:[3]},
  {name:'positive-omitted',total:264,count:1,indices:[]},
  {name:'positive-mixed',total:264,count:2,indices:[3]},
  {name:'all',total:264,count:264,indices:Array.from({length:120},(_,i)=>i)},
  {name:'reset',total:60,count:null,indices:[]},
  {name:'restore',total:264,count:1,indices:[]}
];
(async () => {
  const browser = await chromium.launch({channel:'msedge',headless:true});
  const results = [];
  try {
    for (const target of config.targets) for (const theme of ['light','dark']) for (const width of [736,360]) {
      const page = await browser.newPage({viewport:{width,height:900},colorScheme:theme});
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('https://**/*',route=>route.abort());
      await page.route('http://**/*',route=>route.abort());
      await page.goto(pathToFileURL(target.preview).href);
      const frame = page.frames().find(f=>f.parentFrame());
      await frame.waitForSelector(target.kind === 'generic' ? '#generic-outcome' : '#birthday-primary');
      const inner = await frame.evaluate(()=>window.innerWidth);
      if (inner !== width) {
        await page.setViewportSize({width:width + width - inner,height:900});
        await frame.waitForFunction(w=>window.innerWidth===w,width);
      }
      await frame.evaluate(()=>{window.openai={...window.openai,
        setWidgetState:async()=>{},sendFollowUpMessage:async()=>{throw Error('QA cannot message a task');}};});
      for (const test of cases) {
        if (target.kind === 'generic') {
          await frame.evaluate(t=>syntheticOutcome({total:t.total,matchCount:t.count,visibleMatchIndices:t.indices}),test);
        } else if (test.name === 'pending' || test.name === 'reset') {
          await frame.locator('#birthday-n').fill(String(test.total));
        } else if (test.name === 'restore') {
          await frame.evaluate(t=>window.dispatchEvent(new CustomEvent('openai:set_globals',{
            detail:{globals:{widgetState:{privateContent:{version:2,n:t.total,predictionN:t.total,
              reason:'Synthetic QA only',committed:true,sample:{count:t.count,visibleMatches:t.indices},batch:null}}}}
          })),test);
        } else {
          await frame.locator('#birthday-n').fill(String(test.total));
          await frame.locator('#birthday-reason').fill('Synthetic QA only; not a learner answer.');
          await frame.evaluate(name=>{
            let index = 0;
            Math.random=()=> {
              const at=index++;
              const hit=name==='all' || name==='positive-visible'&&at===3 ||
                name==='positive-omitted'&&at===200 || name==='positive-mixed'&&(at===3||at===200);
              return hit ? 165.1/365 : 0.1;
            };
          },test.name);
          await frame.locator('#birthday-primary').click();
        }
        const seen = await frame.evaluate(kind=>{
          const host = document.getElementById(kind==='generic'?'generic-outcome':'birthday-students');
          const shared=kind!=='original';
          const marks=[...host.querySelectorAll(shared?'[data-zt-sample-mark]':'.birthday-student')];
          const positive=marks.filter(mark=>shared?mark.dataset.matched==='true':mark.classList.contains('is-match'));
          const omitted=shared?Number(host.dataset.omittedMatches):0;
          const count=shared?(host.dataset.matchCount==='unknown'?null:Number(host.dataset.matchCount)):
            Number(document.getElementById('birthday-scene-detail').textContent.match(/本班有 (\d+) 人匹配/)?.[1] || 0);
          const hiddenMark=host.querySelector('[data-zt-omitted-match-mark]');
          const styleTargets=[...positive,...(omitted>0?[hiddenMark]:[])];
          const styleOk=styleTargets.every(mark=>{
            if (!mark || !mark.getClientRects().length || mark.getBoundingClientRect().width===0) return false;
            const css=getComputedStyle(mark);
            return css.backgroundColor!=='rgba(0, 0, 0, 0)' && css.backgroundColor!=='transparent' && css.borderRadius!=='50%';
          });
          return {shown:marks.length,visible:positive.length,omitted:shared&&Number.isFinite(omitted)?omitted:0,
            count,styleOk,overflow:document.documentElement.scrollWidth>window.innerWidth+1,
            hiddenStatesRespected:[...document.querySelectorAll('[hidden]')].every(node=>node.getClientRects().length===0),
            legendOnly:host.querySelectorAll('[data-zt-legend-mark]').length};
        },target.kind);
        const consistent = seen.shown === Math.min(test.total,120) && seen.visible === test.indices.length &&
          (test.count===null || seen.count===test.count && seen.visible+seen.omitted===test.count) && seen.styleOk && !seen.overflow;
        if (target.kind!=='original') assert(consistent,`${target.kind} ${theme} ${width} ${test.name}: ${JSON.stringify(seen)}`);
        if (target.kind!=='original') assert(seen.hiddenStatesRespected,'a hidden state was still visibly rendered');
        if (target.kind==='original' && !['positive-omitted','positive-mixed','all','restore'].includes(test.name))
          assert(consistent,`unexpected original fault ${test.name}: ${JSON.stringify(seen)} expected ${JSON.stringify(test)}`);
        let screenshot = null;
        if (['zero','positive-omitted'].includes(test.name)) {
          await page.waitForTimeout(250);
          screenshot=path.join(config.output,`${target.kind}-${test.name}-${theme}-${width}.png`);
          await page.screenshot({path:screenshot,fullPage:true});
        }
        results.push({artifact:target.artifact,artifact_sha256:target.artifact_sha256,kind:target.kind,
          width,theme,case:test.name,expected:{total:test.total,count:test.count,visible:test.indices.length},
          observed:seen,consistent,screenshot,
          screenshot_sha256:screenshot?createHash('sha256').update(fs.readFileSync(screenshot)).digest('hex'):null});
      }
      assert(!errors.length,errors.join(';'));
      await page.close();
    }
    const hasOriginal=config.targets.some(t=>t.kind==='original');
    const reproduced=results.some(r=>r.kind==='original'&&r.case==='positive-omitted'&&!r.consistent);
    if(hasOriginal) assert(reproduced,'original omitted matches defect was not reproduced');
    fs.writeFileSync(path.join(config.output,'outcome-qa.json'),JSON.stringify({
      synthetic_operations_only:true,no_events_appended_to_learning_log:true,
      original_omitted_matches_defect_reproduced:reproduced,cases:results},null,2));
    process.stdout.write(JSON.stringify({checked:results.length,fixed_cases:results.filter(r=>r.kind!=='original').length,
      report:path.join(config.output,'outcome-qa.json')}));
  } finally {await browser.close();}
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
