// A partial display must account for every real outcome, including zero.
(() => {
  function project({total, matchCount = null, visibleMatchIndices = []}, maxVisible = 120) {
    if (!Number.isSafeInteger(total) || total < 0 || !Number.isInteger(maxVisible) || maxVisible < 1 || maxVisible > 500) {
      throw new Error('Invalid population or display limit');
    }
    const shown = Math.min(total, maxVisible);
    if (!Array.isArray(visibleMatchIndices) || new Set(visibleMatchIndices).size !== visibleMatchIndices.length ||
        visibleMatchIndices.some(i => !Number.isInteger(i) || i < 0 || i >= shown)) {
      throw new Error('Visible match indices must identify distinct shown items');
    }
    const pending = matchCount === null;
    const omitted = total - shown;
    const visibleMatches = visibleMatchIndices.length;
    if (pending ? visibleMatches !== 0 : !Number.isSafeInteger(matchCount) || matchCount < visibleMatches ||
        matchCount > visibleMatches + omitted) {
      throw new Error('Total outcomes do not agree with the displayed and omitted groups');
    }
    const omittedMatches = pending ? null : matchCount - visibleMatches;
    return {total, shown, omitted, matchCount, visibleMatches, omittedMatches,
      visibleMatchIndices: [...visibleMatchIndices],
      state: pending ? 'pending' : matchCount === 0 ? 'zero' :
        visibleMatches === 0 ? 'positive-omitted' : omittedMatches > 0 ? 'positive-mixed' : 'positive-visible'};
  }

  function mount(container, {maxVisible = 120, itemLabel = '对象', matchLabel = '符合条件'} = {}) {
    if (!container) throw new Error('Outcome scene container is required');
    container.classList.add('zt-outcome-host');
    const style = document.createElement('style');
    style.textContent = `.zt-outcome-host {display:grid;gap:8px;min-width:0;color:var(--foreground)}
.zt-outcome-host .zt-outcome-grid {display:grid;grid-template-columns:repeat(auto-fill,minmax(18px,1fr));gap:6px;min-width:0}
.zt-outcome-host .zt-outcome-mark {aspect-ratio:1;max-height:22px;border-radius:50%;background:var(--muted)}
.zt-outcome-host .zt-outcome-mark[data-matched=true] {border-radius:3px;background:var(--viz-series-1)}
.zt-outcome-host .zt-outcome-key {display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.zt-outcome-host .zt-outcome-symbol {width:14px;height:14px;flex:none;border-radius:3px;background:var(--viz-series-1)}
.zt-outcome-host p {margin:0;overflow-wrap:anywhere}
.zt-outcome-host [hidden] {display:none !important}`;
    const grid = document.createElement('div');
    grid.className = 'zt-outcome-grid'; grid.setAttribute('role', 'img');
    grid.dataset.ztOutcomeGrid = '';
    const detail = document.createElement('p');
    detail.dataset.ztOutcomeDetail = ''; detail.setAttribute('aria-live', 'polite');
    const omitted = document.createElement('div'); omitted.className = 'zt-outcome-key';
    omitted.dataset.ztOutcomeOmitted = '';
    const omittedSymbol = document.createElement('span'); omittedSymbol.className = 'zt-outcome-symbol';
    omittedSymbol.dataset.ztOmittedMatchMark = ''; omittedSymbol.setAttribute('aria-hidden', 'true');
    const omittedText = document.createElement('span');
    omitted.append(omittedSymbol, omittedText);
    const legend = document.createElement('div'); legend.className = 'zt-outcome-key text-small';
    const legendSymbol = document.createElement('span'); legendSymbol.className = 'zt-outcome-symbol';
    legendSymbol.dataset.ztLegendMark = ''; legendSymbol.setAttribute('aria-hidden', 'true');
    const legendText = document.createElement('span');
    legendText.textContent = '方形标记示意：' + matchLabel + '。图例不是本次抽样结果。';
    legend.append(legendSymbol, legendText);
    container.replaceChildren(style, grid, detail, omitted, legend);
    return {
      render(data) {
        const summary = project(data, maxVisible);
        const indices = new Set(summary.visibleMatchIndices);
        const marks = document.createDocumentFragment();
        for (let i = 0; i < summary.shown; i++) {
          const mark = document.createElement('span'); mark.className = 'zt-outcome-mark';
          mark.dataset.ztSampleMark = String(i); mark.dataset.matched = String(indices.has(i));
          mark.setAttribute('aria-hidden', 'true'); marks.append(mark);
        }
        grid.replaceChildren(marks);
        container.dataset.outcomeState = summary.state;
        container.dataset.total = String(summary.total);
        container.dataset.shown = String(summary.shown);
        container.dataset.omitted = String(summary.omitted);
        container.dataset.matchCount = summary.matchCount === null ? 'unknown' : String(summary.matchCount);
        container.dataset.visibleMatches = String(summary.visibleMatches);
        container.dataset.omittedMatches = summary.omittedMatches === null ? 'unknown' : String(summary.omittedMatches);
        const statement = summary.state === 'pending' ? '尚未抽样。' : summary.state === 'zero'
          ? '本次匹配为 0，样本中没有方形亮点。' : `本次${matchLabel}共 ${summary.matchCount} 个。`;
        detail.textContent = statement + (summary.omitted ? `展开前 ${summary.shown} 个${itemLabel}。` : `共 ${summary.total} 个${itemLabel}。`);
        omitted.hidden = summary.omitted === 0;
        omittedSymbol.hidden = !(summary.omittedMatches > 0);
        omittedText.textContent = `未展开部分：${summary.omitted} 个${itemLabel}` +
          (summary.state === 'pending' ? '，尚未抽样。' : `，其中 ${summary.omittedMatches} 个${matchLabel}。`);
        grid.setAttribute('aria-label', `${summary.shown} 个已展开${itemLabel}，` +
          (summary.state === 'pending' ? '尚未抽样' : `${summary.visibleMatches} 个${matchLabel}`));
        return summary;
      }
    };
  }
  globalThis.ZepTeachOutcome = {project, mount};
})();
