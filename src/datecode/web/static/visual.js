function renderVisual(target, data) {
    const sheet = node('div',undefined,'film');
    const chosen = [...data.rows].sort((a,b) => b.estimate - a.estimate).slice(0,9);
    for (const record of chosen) {
        const frame = node('button',undefined,'frame');
        frame.dataset.action = `${record.state !== '观察'}`;
        frame.append(node('span',record.key),node('small',`${format.format(record.estimate)} 缺陷估计`));
        frame.addEventListener('click',() => inspect(record));
        sheet.append(frame);
    }
    target.append(sheet);
}
