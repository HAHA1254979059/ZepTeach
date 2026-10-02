// Isolated browser QA. Mock messages never reach a learning task or journal.
const fs = require('fs');
const path = require('path');
const {pathToFileURL} = require('url');
const {createHash} = require('crypto');
const {chromium} = require(process.argv[2]);
const config = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const assert = (value, message) => { if (!value) throw new Error(message); };
async function capture(page, frame, test, width, phase) {
  await page.waitForTimeout(300);
  const measured = await frame.evaluate(({actual, ordinary, width, phase}) => {
    const visible = element => !!element && element.getClientRects().length > 0 &&
      element.getBoundingClientRect().width > 0 && element.getBoundingClientRect().height > 0;
    const overflowing = [...document.body.querySelectorAll('*')].filter(visible).filter(element => {
      const bounds = element.getBoundingClientRect();
      return bounds.left < -1 || bounds.right > window.innerWidth + 1;
    }).map(element => element.tagName + '#' + element.id);
    const scene = document.querySelector(actual ? '#birthday-students' : '[data-zt-scene]');
    let fieldsOrdered = true;
    let fieldsTop = null;
    if (actual) {
      const number = document.querySelector('#birthday-n');
      const reason = document.querySelector('#birthday-reason');
      fieldsTop = number?.getBoundingClientRect().top;
      fieldsOrdered = !!number && !!reason && reason.getBoundingClientRect().top >= number.getBoundingClientRect().bottom;
    } else if (!ordinary) {
      const fields = document.querySelector('[data-zt-fields]');
      const labels = [...fields.children].filter(visible);
      const reason = document.querySelector('[name=reason]').closest('label');
      fieldsTop = fields.getBoundingClientRect().top;
      fieldsOrdered = labels.every((label, i) => i === 0 || label.getBoundingClientRect().top >= labels[i - 1].getBoundingClientRect().bottom) &&
        reason.getBoundingClientRect().top >= fields.getBoundingClientRect().bottom;
    }
    const primary = [...document.querySelectorAll(ordinary ? '#zepteach-input button' : 'button.btn-primary')].filter(visible);
    return {innerWidth: window.innerWidth, contentHeight: document.body.scrollHeight, overflowing,
      checks: {inner_width_matches: window.innerWidth === width,
        hidden_states_respected:[...document.querySelectorAll('[hidden]')].every(node=>node.getClientRects().length===0),
        no_horizontal_overflow: document.documentElement.scrollWidth <= window.innerWidth + 1,
        no_dom_overflow: overflowing.length === 0,
        scene_visible: visible(scene), fields_ordered: fieldsOrdered,
        scene_before_fields: !!scene && fieldsTop != null && scene.getBoundingClientRect().bottom <= fieldsTop,
        one_primary_action: primary.length === 1, interaction_verified: phase === 'interacted'}};
  }, {actual: !!test.actual, ordinary: !!test.ordinary, width, phase});
  measured.checks.frame_content_fits = (await page.locator('iframe').evaluate(element => element.clientHeight)) >= measured.contentHeight - 2;
  for (const [key, passed] of Object.entries(measured.checks)) {
    if (key === 'interaction_verified' && phase === 'initial' || key === 'one_primary_action' && phase !== 'initial') continue;
    if (test.ordinary && ['scene_visible', 'scene_before_fields'].includes(key)) continue;
    assert(passed, `${test.name} ${phase} ${width}: ${key} failed ${JSON.stringify(measured)}`);
  }
  const screenshot = path.join(config.output, test.name + '-' + phase + '-' + width + '.png');
  await page.screenshot({path: screenshot, fullPage: true});
  return {...measured, screenshot, screenshot_sha256: createHash('sha256').update(fs.readFileSync(screenshot)).digest('hex')};
}
(async () => {
  const browser = await chromium.launch({channel: 'msedge', headless: true});
  const results = [];
  try {
    for (const test of config.cases) {
      for (const width of [736, 360]) {
        const page = await browser.newPage({viewport: {width, height: 900}});
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.route('http://**/*', route => route.abort());
        await page.route('https://**/*', route => route.abort());
        await page.goto(pathToFileURL(test.preview).href);
        const frame = page.frames().find(item => item.parentFrame());
        assert(frame, 'sandbox frame missing');
        await frame.waitForSelector(test.actual ? '#birthday-lab-one' : test.ordinary ? '#zepteach-input textarea' : '[data-zt-prediction]');
        const currentInnerWidth = await frame.evaluate(() => window.innerWidth);
        if (currentInnerWidth !== width) {
          const viewport = page.viewportSize();
          await page.setViewportSize({width: viewport.width + width - currentInnerWidth, height: viewport.height});
          await frame.waitForFunction(expected => window.innerWidth === expected, width);
        }
        await frame.evaluate(() => {
          window.__testPackets = [];
          window.__testStates = [];
          window.openai = {...window.openai,
            setWidgetState: async state => { window.__testStates.push(state); window.openai.widgetState = state; },
            sendFollowUpMessage: async data => { window.__testPackets.push(data.prompt); }};
        });
        const initial = await capture(page, frame, test, width, 'initial');
        if (test.ordinary) {
          await frame.locator('#zepteach-input textarea').fill('Synthetic keyboard answer');
          await frame.locator('#zepteach-input textarea').press('Control+Enter');
          const packet = await frame.evaluate(() => window.__testPackets.at(-1));
          assert(packet?.includes('Synthetic keyboard answer'), 'ordinary sandbox keyboard submission failed');
        } else if (test.actual) {
          if (await frame.locator('#birthday-primary').count()) {
            assert(await frame.locator('#birthday-batch').isHidden(), 'batch visible before prediction');
            await frame.locator('#birthday-primary').click();
            assert(await frame.locator('#birthday-batch').isHidden(), 'missing reason unlocked experiment');
            await frame.locator('#birthday-n').fill('100');
            await frame.locator('#birthday-reason').fill('Synthetic browser QA only; not a learner answer.');
            await frame.locator('#birthday-primary').click();
            assert(await frame.locator('#birthday-batch').isVisible(), 'prediction did not unlock batch');
            assert(await frame.locator('#birthday-students span').count() === 100, 'single class not drawn');
            await frame.locator('#birthday-r').selectOption('100');
            await frame.locator('#birthday-repeat').click();
            assert((await frame.locator('#birthday-rounds').textContent()) === '100', 'repeat count not shown');
            assert(await frame.locator('#birthday-stats').isVisible(), 'batch statistics not shown');
            await frame.locator('#birthday-share').click();
            assert((await frame.evaluate(() => window.__testPackets.at(-1)))?.includes('Synthetic browser QA only'), 'current experiment did not send actual reason');
          } else {
          assert(await frame.locator('#birthday-simulation').isHidden(), 'simulation visible before prediction');
          await frame.locator('#birthday-submit').click();
          assert(await frame.locator('#birthday-simulation').isHidden(), 'invalid prediction unlocked simulator');
          await frame.locator('#birthday-prediction').fill('100');
          await frame.locator('#birthday-reason').fill('Synthetic browser QA only; not a learner answer.');
          await frame.locator('#birthday-submit').click();
          assert(await frame.locator('#birthday-simulation').isVisible(), 'valid prediction did not unlock');
          await frame.locator('#birthday-single').click();
          assert(await frame.locator('#birthday-dots span').count() === 100, 'single class not drawn');
          await frame.locator('#birthday-r').fill('200');
          await frame.locator('#birthday-batch').click();
          assert(await frame.locator('#birthday-compare').isVisible(), 'batch output absent');
          assert((await frame.locator('#birthday-batch-result').textContent()).includes('200'), 'repeat count not shown');
          }
        } else {
          const labRoot = frame.locator('section[aria-label="交互学习环节"]');
          assert(await frame.locator('[data-zt-simulation]').isHidden(), 'simulation prematurely unlocked');
          assert(await frame.locator('[data-zt-reflection]').isHidden(), 'completion prematurely available');
          await frame.locator('[data-zt-predict]').click();
          assert(await frame.locator('[data-zt-simulation]').isHidden(), 'invalid prediction unlocked');
          if (test.choice) {
            await frame.locator('[name=policy]').selectOption('b');
            await frame.locator('[name=assumption]').fill('Synthetic assumption');
            await frame.locator('[name=confidence]').fill('65');
          } else await frame.locator('[name=capacity]').fill('12');
          await frame.locator('[name=reason]').fill('Synthetic browser QA only.');
          await frame.locator('[data-zt-predict]').click();
          assert(await frame.locator('[data-zt-simulation]').isVisible(), 'valid prediction did not unlock: ' +
            await frame.locator('[data-zt-status]').textContent() + ' errors=' + errors.join(';') +
            ' validity=' + await frame.locator('[data-zt-prediction]').evaluate(form => [...form.elements].map(e => [e.name, e.value, e.validationMessage])));
          await frame.locator('[data-fixture-run]').click();
          await frame.locator('[data-fixture-batch]').click();
          assert((await frame.locator('[data-fixture-result]').textContent()).includes('8'), 'batch calculation did not update result');
          assert(await frame.locator('[data-zt-reflection]').isVisible(), 'reflection did not unlock');
          // A send request is not an on-disk acknowledgement; resend uses the same IDs.
          await frame.locator('[data-zt-send]').click();
          const first = await frame.evaluate(() => window.__testPackets.at(-1));
          await frame.locator('[data-zt-send]').click();
          const second = await frame.evaluate(() => window.__testPackets.at(-1));
          assert(first === second, 'retry changed event identities');
          const packet = JSON.parse(first.replace('[ZepTeach interaction] ', ''));
          assert(packet.events.length === 3, 'answer and two actual synthetic actions not captured');
          if (test.choice) assert(packet.events[0].confidence_if_supplied === 65, 'supplied confidence lost');
          else assert(!('confidence_if_supplied' in packet.events[0]), 'invented confidence');
          // A different saved scope must not restore answers into this activity.
          const state = await frame.evaluate(() => window.__testStates.at(-1));
          await frame.evaluate(saved => window.dispatchEvent(new CustomEvent('openai:set_globals', {
            detail: {globals: {widgetState: saved}}
          })), state);
          assert(await labRoot.evaluate(root => root.ztInteractive.phase) === 'exploring', 'state restoration changed phase');
          const observation = '  Synthetic observation; ask teacher to check.  ';
          await frame.locator('[data-zt-observation]').fill(observation);
          await frame.locator('[data-zt-confirm]').click();
          const confirmed = await frame.evaluate(() => window.__testPackets.at(-1));
          assert(JSON.parse(confirmed.replace('[ZepTeach interaction] ', '')).events.at(-1).actual_user_input === observation,
            'actual observation text was normalized or changed');
          assert(await labRoot.evaluate(root => root.ztInteractive.phase) === 'review_requested', 'confirmation not pending teacher check');
          assert(await frame.locator('[data-zt-confirm]').isDisabled(), 'confirmation duplicated');
          await frame.evaluate(() => {window.openai.sendFollowUpMessage = async () => {throw new Error('synthetic send failure');};});
          await frame.locator('[data-zt-send]').click();
          assert(await frame.locator('[data-zt-manual]').isVisible(), 'failed send did not preserve packet');
          await frame.evaluate(() => {delete window.openai.sendFollowUpMessage;});
          await frame.locator('[data-zt-send]').click();
          assert(await frame.locator('[data-zt-manual]').isVisible(), 'missing bridge fallback absent');
          assert((await frame.locator('[data-zt-packet]').inputValue()).startsWith('[ZepTeach interaction] '), 'fallback omitted actual packet');
        }
        const overflow = await frame.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
        assert(!overflow, 'horizontal clipping at ' + width);
        assert(!errors.length, 'runtime errors: ' + errors.join('; '));
        const interacted = await capture(page, frame, test, width, 'interacted');
        results.push({artifact: test.artifact,
          artifact_sha256: test.artifact_sha256,
          width, controls_verified: true, frame_content_fits: true,
          no_horizontal_overflow: true, page_errors: errors, initial, interacted,
          synthetic_operations_only: true, learner_visibility: 'unconfirmed'});
        await page.close();
      }
    }
    fs.writeFileSync(path.join(config.output, 'browser-qa.json'), JSON.stringify({
      purpose: 'isolated development preview', synthetic_operations_only: true,
      no_events_appended_to_learning_log: true, cases: results}, null, 2));
    process.stdout.write(JSON.stringify({passed: results.length, report: path.join(config.output, 'browser-qa.json')}));
  } finally { await browser.close(); }
})().catch(error => {process.stderr.write(error.stack); process.exitCode = 1;});
