const fs = require('fs');
const path = require('path');
const {pathToFileURL} = require('url');
const {chromium} = require(process.argv[2]);
const cfg = JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
const assert = (yes,reason) => {if(!yes)throw Error(reason);};
(async()=>{
 const browser = await chromium.launch({channel:'msedge',headless:true});
 const results=[];
 try {
  for(const mode of ['touch_preview','no_javascript','missing_host_styles','missing_return']) {
   const context=await browser.newContext({viewport:{width:390,height:900},isMobile:true,hasTouch:true,
       javaScriptEnabled:mode!=='no_javascript'});
   const page=await context.newPage();
   await page.route('https://**/*',r=>r.abort());
   await page.goto(pathToFileURL(mode==='missing_host_styles'?cfg.bare:mode==='no_javascript'?cfg.no_script:cfg.normal).href);
   const frame=page.frames().find(f=>f.parentFrame());
   await frame.waitForSelector('[data-zt-title]');
   assert((await frame.locator('[data-zt-prompt]').textContent()).includes('Predict the size'),'essential question missing');
   assert(await frame.locator('[name=size]').count()===1,'named prediction field missing');
   if(mode==='no_javascript') {
     assert(await frame.locator('[data-zt-predict]').isDisabled(),'script-disabled action appeared usable');
     assert(await frame.locator('noscript').isVisible(),'no-script guidance absent');
   } else if(mode==='missing_host_styles') {
     assert(await frame.locator('[data-zt-predict]').isDisabled(),'missing styles did not select fallback');
     assert((await frame.locator('[data-zt-status]').textContent()).includes('对话正文'),'honest fallback guidance absent');
   } else {
     assert(!(await frame.locator('[data-zt-predict]').isDisabled()),'supported preview did not enable action');
     await frame.locator('[name=size]').fill('12.5');
     await frame.locator('[name=reason]').fill('Synthetic capability QA only.');
     await frame.locator('[data-zt-predict]').click();
     assert(await frame.locator('[data-zt-simulation]').isVisible(),'numeric semantics changed or prediction not committed');
     if(mode==='missing_return') {
       await frame.evaluate(()=>{delete window.openai.sendFollowUpMessage;});
       await frame.evaluate(()=>document.querySelector('section[aria-label="交互学习环节"]').ztInteractive.perform(
         {id:'qa',label:'Synthetic QA action'},()=>({observed_ui_behavior:'Synthetic result only',values:{count:0}})));
       await frame.locator('[data-zt-send]').click();
       assert(await frame.locator('[data-zt-manual]').isVisible(),'return fallback absent');
       assert((await frame.locator('[data-zt-packet]').inputValue()).startsWith('[ZepTeach interaction] '),'actual buffered input not preserved');
     }
   }
   const screenshot=path.join(cfg.output,mode+'.png');
   await page.screenshot({path:screenshot,fullPage:true});
   results.push({mode,passed:true,screenshot,artifact_sha256:cfg.artifact_sha256,
      synthetic_operations_only:true,actual_mobile_app_verified:false,actual_client_return_verified:false});
   await context.close();
  }
  fs.writeFileSync(path.join(cfg.output,'presentation-qa.json'),JSON.stringify({
     actual_mobile_app_verified:false,no_events_appended_to_learning_log:true,cases:results},null,2));
  process.stdout.write(JSON.stringify({passed:results.length,actual_mobile_app_verified:false,
    report:path.join(cfg.output,'presentation-qa.json')}));
 } finally {await browser.close();}
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
