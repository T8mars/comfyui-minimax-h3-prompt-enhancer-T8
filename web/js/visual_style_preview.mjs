// Original, local vector illustrations. No user images, model calls or workflow writes.
const NS = 'http://www.w3.org/2000/svg';
export const DIAGRAM_LABELS = Object.freeze({
    sequence: '动作过程 / Action continuity', frame: '框中框 / Frame within frame', push: '缓慢推进 / Dolly in',
    perspective: '空间透视 / Perspective', fixed: '固定观察 / Fixed camera', negative: '主体与留白 / Negative space',
    track: '连续跟随 / Tracking', reflection: '主体与反射 / Reflection', wide: '环境与尺度 / Environmental scale',
    symmetry: '对称构图 / Symmetry', depth: '纵深关系 / Depth', pov: '主观观察位置 / POV', close: '局部近看 / Close view',
    lateral: '横向移动 / Lateral move', staging: '主体间距 / Staging', diagonal: '斜线构图 / Diagonals',
    detail: '已有细节 / Existing detail', handheld: '克制手持 / Controlled handheld', hold: '持续观察 / Sustained observation',
    overhead: '较高观察位置 / Elevated view', orbit: '围绕既有主体 / Orbit', low: '较低观察位置 / Low viewpoint',
    cuts: '允许的切点 / Permitted cuts', crane: '机位升降 / Camera elevation', center: '观看中心 / Visual center',
    outline: '轮廓可读性 / Readable outline', layers: '前中后层次 / Spatial layers', parallel: '已有双线 / Existing parallel lines',
    portrait: '肖像观察 / Portrait framing', occlusion: '前景遮挡 / Foreground occlusion', attention: '注意力转移 / Attention',
    flat: '平面关系 / Planar composition', gesture: '动作与物件关系 / Gesture and object', gaze: '观看与接收 / Gaze and response',
    sound: '已有声源位置 / Existing sound position', repeat: '已有重复的差别 / Existing repetition',
    eye_level: '既定观察高度 / Given eye level', beat: '已有节奏 / Existing rhythm', zoom: '克制变焦 / Restrained zoom',
});
export const LIGHT_LABELS = Object.freeze({
    localized: '局部色光 / Localized color light', rim: '侧背或轮廓光 / Back / rim light', top: '顶部光 / Top light',
    hard_side: '定向亮暗 / Directional contrast', soft_side: '侧向或方向光 / Side / directional light',
    flat: '均匀光 / Even light', available: '保留可用光 / Available light', diffuse: '漫射光 / Diffuse light',
});
let nextSVG = 0;
const clamp = value => Math.min(1, Math.max(0, Number.isFinite(value) ? value : 0));
const html = (tag, text, parent) => {const el = document.createElement(tag); if (text) el.textContent = text; parent?.append(el); return el;};
const svgEl = (tag, attrs, parent, text) => {
    const el = document.createElementNS(NS, tag);
    for (const [key, value] of Object.entries(attrs || {})) el.setAttribute(key, String(value));
    if (text) el.textContent = text;
    parent?.append(el); return el;
};
const rect = (p, x, y, width, height, fill, extra = {}) => svgEl('rect', {x, y, width, height, fill, ...extra}, p);
const line = (p, x1, y1, x2, y2, stroke = '#c6d4dc', extra = {}) => svgEl('line', {x1, y1, x2, y2, stroke, 'stroke-width': 2, ...extra}, p);
const label = (p, x, y, text, size = 12, fill = '#edf2f5') => svgEl('text', {x, y, fill, 'font-size': size, 'font-family': 'system-ui,sans-serif'}, p, text);
function arrow(p, x1, y1, x2, y2, dashed = false) {
    line(p, x1, y1, x2, y2, '#eef4f8', dashed ? {'stroke-dasharray': '5 5'} : {});
    const angle = Math.atan2(y2 - y1, x2 - x1), back = 9;
    const a = [x2 - back * Math.cos(angle - .5), y2 - back * Math.sin(angle - .5)];
    const b = [x2 - back * Math.cos(angle + .5), y2 - back * Math.sin(angle + .5)];
    svgEl('polygon', {points: `${x2},${y2} ${a.join(',')} ${b.join(',')}`, fill: '#eef4f8'}, p);
}
function figure(p, x, y, scale = 1, cloth = '#b8c0c5', skin = '#d8d1c7', name = '') {
    const g = svgEl('g', {transform: `translate(${x} ${y}) scale(${scale})`}, p);
    svgEl('ellipse', {cx: 0, cy: 2, rx: 16, ry: 4, fill: '#10171b', opacity: .22}, g);
    line(g, -6, -21, -8, 0, cloth, {'stroke-width': 7}); line(g, 6, -21, 9, 0, cloth, {'stroke-width': 7});
    rect(g, -11, -49, 22, 32, cloth, {rx: 7});
    svgEl('circle', {cx: 0, cy: -60, r: 9, fill: skin}, g);
    if (name) label(g, -4, -78, name, 12);
    return g;
}
function rootSVG(parent, title) {
    const svg = svgEl('svg', {viewBox: '0 0 400 225', role: 'img', 'aria-label': title, preserveAspectRatio: 'xMidYMid meet'}, parent);
    svg.style.cssText = 'display:block;width:100%;height:auto;aspect-ratio:16/9;border-radius:9px;background:#192229';
    svgEl('title', {}, svg, title); return svg;
}
function gradient(svg, colors, vertical = false) {
    const defs = svgEl('defs', {}, svg), id = `t8-style-gradient-${++nextSVG}`;
    const grad = svgEl('linearGradient', {id, x1: '0%', y1: '0%', x2: vertical ? '0%' : '100%', y2: vertical ? '100%' : '0%'}, defs);
    colors.forEach(([color, opacity], i) => svgEl('stop', {offset: `${100 * i / (colors.length - 1)}%`, 'stop-color': color, 'stop-opacity': opacity}, grad));
    return `url(#${id})`;
}
function colorScene(svg, palette, scene, light = null) {
    const [wall, floor, window, trim, furniture, backdrop] = palette;
    rect(svg, 0, 0, 400, 225, wall);
    if (scene === 'street') {
        rect(svg, 0, 0, 400, 86, backdrop);
        for (const [x, y, w, h] of [[0, 30, 80, 140], [90, 8, 65, 145], [288, 25, 112, 150]]) {
            rect(svg, x, y, w, h, x === 90 ? furniture : wall);
            for (let row = 0; row < 4; row++) for (let col = 0; col < 3; col++) rect(svg, x + 8 + col * 19, y + 12 + row * 27, 10, 15, window);
        }
        svgEl('polygon', {points: '0,225 145,144 256,144 400,225', fill: floor}, svg);
        svgEl('polygon', {points: '165,225 192,144 206,144 235,225', fill: trim}, svg);
        rect(svg, 287, 99, 100, 12, trim); rect(svg, 303, 116, 63, 58, furniture);
        figure(svg, 250, 198, .9, '#58616c', '#d5b49b');
    } else {
        rect(svg, 0, 173, 400, 52, floor);
        rect(svg, 19, 16, 126, 145, trim, {rx: 2}); rect(svg, 25, 22, 114, 133, window);
        rect(svg, 31, 84, 102, 65, backdrop); rect(svg, 77, 22, 5, 133, trim); rect(svg, 25, 78, 114, 4, trim);
        rect(svg, 213, 101, 155, 48, furniture, {rx: 13}); rect(svg, 202, 135, 177, 36, furniture, {rx: 9});
        rect(svg, 208, 164, 9, 18, trim); rect(svg, 363, 164, 9, 18, trim);
        rect(svg, 83, 182, 100, 9, trim, {rx: 3}); rect(svg, 95, 191, 5, 21, trim); rect(svg, 167, 191, 5, 21, trim);
        rect(svg, 284, 25, 67, 50, trim); rect(svg, 289, 30, 57, 40, backdrop);
        figure(svg, 187, 170, .85, '#58616c', '#d5b49b');
    }
    // Both sides have the exact same neutral relief; only the optional light overlay differs.
    rect(svg, 0, 0, 400, 225, gradient(svg, [['#ffffff', .08], ['#000000', .16]], true));
    if (light === 'localized') rect(svg, 270, 0, 130, 175, gradient(svg, [[window, 0], [window, .48]]));
    if (light === 'rim') {
        rect(svg, 0, 0, 400, 225, '#111820', {opacity: .15});
        line(svg, scene === 'street' ? 259 : 195, 112, scene === 'street' ? 259 : 195, 168, '#fff4d5', {'stroke-width': 3, opacity: .65});
    }
    if (light === 'top') rect(svg, 0, 0, 400, 225, gradient(svg, [['#fff9ea', .36], ['#10151b', .25]], true));
    if (light === 'hard_side') {
        svgEl('polygon', {points: '0,0 145,0 310,225 0,225', fill: '#fff7dc', opacity: .18}, svg);
        svgEl('polygon', {points: '145,0 400,0 400,225 310,225', fill: '#08111c', opacity: .38}, svg);
    }
    if (light === 'soft_side') rect(svg, 0, 0, 400, 225, gradient(svg, [['#fff9e6', .27], ['#142030', .18]]));
    if (light === 'diffuse' || light === 'flat') rect(svg, 0, 0, 400, 225, '#f4eee3', {opacity: light === 'flat' ? .14 : .07});
    // "Available" deliberately keeps the baseline lighting instead of inventing a new source.
}
function stage(svg, code, t) {
    rect(svg, 0, 0, 400, 225, '#202b33');
    rect(svg, 0, 157, 400, 68, '#344149');
    const g = svgEl('g', {}, svg);
    let x = 170, y = 177, scale = 1, second = false;
    if (code === 'push') {scale = 1 + t * .5; x = 170;}
    if (code === 'zoom') {g.setAttribute('transform', `translate(${200 * (1 - (1 + t * .45))} ${112 * (1 - (1 + t * .45))}) scale(${1 + t * .45})`);}
    if (code === 'lateral') g.setAttribute('transform', `translate(${-t * 54} 0)`);
    if (code === 'track' || code === 'handheld') g.setAttribute('transform', `translate(${-t * 50} ${code === 'handheld' ? Math.sin(t * 24) * 2 : 0})`);
    if (code === 'diagonal') g.setAttribute('transform', 'rotate(-9 200 112)');
    if (code === 'wide') {scale = .58; x = 244; y = 176;}
    if (code === 'close' || code === 'portrait') {scale = 2.1; x = 200; y = 244;}
    if (code === 'low') {scale = 1.35; y = 195; x = 215;}
    if (code === 'negative') {x = 291; scale = .8;}
    if (code === 'center' || code === 'symmetry') x = 200;
    if (code === 'staging' || code === 'gaze' || code === 'attention' || code === 'gesture' || code === 'layers' || code === 'flat') {x = 125; second = true;}
    if (code === 'perspective' || code === 'depth' || code === 'push' || code === 'pov') {
        for (let n = 0; n < 4; n++) {const offset = n * 24; rect(g, offset, offset * .42, 400 - 2 * offset, 192 - offset * .6, 'none', {stroke: '#667782', 'stroke-width': 2});}
        for (const corner of [[0, 0], [400, 0], [0, 225], [400, 225]]) line(g, ...corner, 205, 98, '#52646e');
    } else {
        rect(g, 38, 32, 78, 112, '#536570'); rect(g, 45, 39, 64, 98, '#85949b');
        rect(g, 288, 46, 62, 108, '#152029');
        line(g, 0, code === 'low' ? 180 : code === 'overhead' ? 100 : 157, 400, code === 'low' ? 180 : code === 'overhead' ? 100 : 157, '#74858f');
    }
    if (code === 'symmetry') {rect(g, 284, 32, 78, 112, '#536570'); line(g, 200, 12, 200, 213, '#a9bbc4', {'stroke-dasharray': '4 6'});}
    if (code === 'frame' || code === 'occlusion' || code === 'negative') {
        rect(g, 0, 0, code === 'negative' ? 228 : 70, 225, '#101a22', {opacity: code === 'negative' ? .2 : .9});
        rect(g, 330, 0, 70, 225, '#101a22'); rect(g, 0, 0, 400, 26, '#101a22');
    }
    if (code === 'layers' || code === 'flat') {
        rect(g, 16, 73, 368, 43, 'none', {stroke: '#7b8990', 'stroke-dasharray': '5 4'});
        label(g, 25, 96, 'BACK', 10); rect(g, 14, 191, 94, 25, '#17232b'); label(g, 20, 208, 'FRONT', 10);
    }
    if (code === 'overhead') {svgEl('ellipse', {cx: 205, cy: 151, rx: 100, ry: 42, fill: 'none', stroke: '#9baab2'}, g); scale = .65; x = 205; y = 155;}
    if (code === 'track' || code === 'handheld') x += t * 50;
    figure(g, x, y, scale, code === 'outline' ? '#eef2f4' : '#b8c0c5', '#c8ccd0', 'A');
    if (second) figure(g, 278, code === 'flat' ? y : y - 23, code === 'layers' ? .66 : .84, '#939fa6', '#c8ccd0', 'B');
    if (code === 'reflection') {
        rect(g, 264, 24, 91, 169, '#50606a', {stroke: '#d0dae0', 'stroke-width': 3});
        figure(g, 306, 165, .75, '#97a4ad', '#bec5ca'); label(svg, 266, 209, 'REFLECTION', 10);
        line(svg, 181, 125, 298, 125, '#d1dce2', {'stroke-dasharray': '4 5'});
    }
    if (code === 'detail' || code === 'gesture') {
        rect(g, 190, 146, 40, 8, '#d6dce0', {rx: 3}); rect(svg, 174, 119, 72, 66, 'none', {stroke: '#edf3f7', 'stroke-dasharray': '5 4'});
        label(svg, 174, 109, 'EXISTING DETAIL', 10); if (code === 'gesture') arrow(svg, 144, 135, 193, 149);
    }
    if (code === 'gaze') {arrow(svg, 135, 112, 259, 104, true); arrow(svg, 260, 121, 137, 129, true);}
    if (code === 'attention') {const target = t < .5 ? 125 : 278; svgEl('circle', {cx: target, cy: target === 125 ? 117 : 105, r: 34, fill: 'none', stroke: '#eef5fa', 'stroke-width': 2}, svg);}
    if (code === 'pov') {line(svg, 184, 110, 216, 110); line(svg, 200, 94, 200, 126); label(svg, 11, 23, 'EXISTING POV', 11);}
    if (code === 'eye_level') {line(svg, 20, 117, 380, 117, '#d4dee5', {'stroke-dasharray': '7 5'}); label(svg, 232, 106, 'GIVEN EYE LEVEL', 10);}
    if (code === 'orbit') {
        svgEl('ellipse', {cx: 190, cy: 167, rx: 108, ry: 35, fill: 'none', stroke: '#d3dfe6', 'stroke-dasharray': '6 5'}, svg);
        const angle = (-.8 + 1.6 * t) * Math.PI; svgEl('circle', {cx: 190 + 108 * Math.cos(angle), cy: 167 + 35 * Math.sin(angle), r: 7, fill: '#fff'}, svg);
        label(svg, 20, 23, 'CAMERA PATH', 11);
    }
    if (['push', 'track', 'handheld', 'lateral', 'crane', 'zoom'].includes(code)) {
        if (code === 'push' || code === 'zoom') arrow(svg, 200, 210, 200, 175);
        else if (code === 'crane') {arrow(svg, 363, 191, 363, 43); rect(svg, 348, 176 - t * 120, 29, 18, '#ebf1f4', {rx: 3});}
        else arrow(svg, 30, 205, 130, 205);
        label(svg, 16, 22, code === 'zoom' ? 'ZOOM (FIXED POSITION)' : 'CAMERA MOVEMENT', 10);
    }
}
const TIMELINES = new Set(['sequence', 'hold', 'cuts', 'parallel', 'repeat', 'beat', 'sound']);
const MOTION = new Set(['push', 'zoom', 'lateral', 'track', 'handheld', 'attention', 'orbit', 'crane', ...TIMELINES]);
function timeline(svg, code, t) {
    rect(svg, 0, 0, 400, 225, '#202b33');
    const titles = code === 'repeat' ? ['A', "A′", 'DIFFERENCE'] : ['BEFORE', 'ACTION', 'AFTER'];
    for (let i = 0; i < 3; i++) {
        const x = 16 + i * 128;
        rect(svg, x, 37, 112, 105, '#34454f', {rx: 8, stroke: '#687d89'});
        figure(svg, x + 42 + (code === 'hold' ? 0 : i * 13), 132, .85, '#c4cdd3', '#d9dcdf'); label(svg, x + 8, 57, titles[i], 10);
        if (i < 2) arrow(svg, x + 114, 90, x + 125, 90);
    }
    const y = code === 'parallel' ? 176 : 181;
    rect(svg, 16, y, 368, 7, '#667883', {rx: 3});
    if (code === 'cuts') for (const x of [139, 262]) line(svg, x, 165, x, 199, '#f6f9fb', {'stroke-width': 3});
    if (code === 'parallel') {rect(svg, 16, 196, 368, 7, '#899aa4', {rx: 3}); label(svg, 16, 166, 'EXISTING A / B', 10);}
    if (code === 'beat') for (let i = 0; i < 12; i++) line(svg, 24 + i * 30, 160, 24 + i * 30, 171 - (i % 3) * 8, '#cfdbe2');
    if (code === 'sound') {label(svg, 16, 166, 'ON / OFF SCREEN · EXISTING SOUND ONLY', 10);}
    svgEl('circle', {cx: 16 + 368 * t, cy: y + 3, r: 6, fill: '#f3f7fa'}, svg);
    label(svg, 16, 218, code === 'cuts' ? 'CUTS ONLY WHEN ALLOWED' : ['hold', 'sequence'].includes(code)
        ? 'CONTINUOUS OBSERVATION · NOT CUTS' : 'RELATIVE PROGRESS · NOT SECONDS', 10);
}
export function validIllustration(data, kind, resource, digest) {
    return data?.available === true && data.schema_version === 't8-style-illustrations/v1' && data.revision === '1.0.0'
        && data.kind === kind && data.id === resource.id && data.resource_sha256 === digest && data.real_output === false
        && /^[a-f0-9]{64}$/.test(digest) && (kind === 'color'
            ? Object.hasOwn(LIGHT_LABELS, data.lighting) && Array.isArray(data.methods) && data.methods.length === 0
            : data.lighting === null && Array.isArray(data.methods) && data.methods.length === resource.methods.length
                && data.methods.every(code => Object.hasOwn(DIAGRAM_LABELS, code)));
}

export function renderVisualPreview(parent, {kind, resource, illustration, digest, scope, isLive = () => true}) {
    const root = html('section', '', parent); root.className = 't8-style-illustration';
    root.dataset.kind = kind; root.dataset.styleId = resource.id;
    const badge = html('p', '本地示意 · 非模型实测 / LOCAL ILLUSTRATION · NOT A MODEL OUTPUT', root);
    badge.style.cssText = 'color:#c8ddec;font-size:11px;letter-spacing:.06em;margin:8px 0';
    if (!validIllustration(illustration, kind, resource, digest)) {
        html('p', '示意资源暂不可用或版本不匹配；下方文字与风格选择仍可使用。 / Illustration unavailable; the validated style remains selectable.', root);
        return () => {};
    }
    const controls = html('div', '', root); controls.className = 't8-style-preview-controls';
    controls.style.cssText = 'display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:12px 0';
    const grid = html('div', '', root); grid.style.cssText = 'display:grid;grid-template-columns:repeat(auto-fit,minmax(min(220px,100%),1fr));gap:12px';
    const left = html('div', '', grid), right = html('div', '', grid);
    const leftTitle = html('p', '', left), rightTitle = html('p', '', right);
    leftTitle.style.cssText = rightTitle.style.cssText = 'margin:4px 0 8px;font-size:12px;color:#d3dfe6';
    const leftHost = html('div', '', left), rightHost = html('div', '', right);
    const explanation = html('p', '', root); explanation.style.cssText = 'font-size:12px;line-height:1.6;white-space:pre-wrap';
    let disposed = false, frame = 0, playing = false, progress = .5, selected = 0;
    const alive = () => !disposed && isLive();
    let draw = () => {};
    let pause = () => {};
    const visibilityChanged = () => {if (document.hidden) pause();};
    const dispose = () => {
        disposed = true; playing = false; if (frame) cancelAnimationFrame(frame); frame = 0;
        document.removeEventListener('visibilitychange', visibilityChanged);
    };
    const button = (text, fn) => {const b = html('button', text, controls); b.type = 'button'; b.onclick = () => {if (alive()) fn();}; return b;};
    if (kind === 'color') {
        let scene = 'room', lighting = scope === '色彩 + 光影 / Color + lighting';
        const sceneSelect = html('select', '', controls); sceneSelect.setAttribute('aria-label', '预览场景 / Preview scene');
        for (const [value, text] of [['room', '室内 / Interior'], ['street', '街景 / Street']]) html('option', text, sceneSelect).value = value;
        const lightButton = button('', () => {lighting = !lighting; draw();});
        sceneSelect.onchange = () => {if (alive()) {scene = sceneSelect.value === 'street' ? 'street' : 'room'; draw();}};
        draw = () => {
            leftHost.replaceChildren(); rightHost.replaceChildren();
            leftTitle.textContent = '中性基准 / Neutral baseline'; rightTitle.textContent = lighting ? '配色 + 光影示意 / Palette + lighting' : '仅配色示意 / Palette only';
            lightButton.textContent = lighting ? '光影示意：开 / Light: On' : '光影示意：关 / Light: Off';
            lightButton.setAttribute('aria-pressed', String(lighting));
            colorScene(rootSVG(leftHost, leftTitle.textContent), ['#9aa4ab', '#74828b', '#b5c3cc', '#526773', '#788a95', '#d1d7db'], scene);
            colorScene(rootSVG(rightHost, rightTitle.textContent), resource.primary.map(c => c.hex), scene, lighting ? illustration.lighting : null);
            explanation.textContent = '同一矢量场景，仅演示颜色关系；人物肤色与衣服保持不变。场景比例不是色卡占比，也不是对用户图片套 LUT。\nSame vector scene; clothing and skin stay fixed. Not pixel quotas or an image filter.'
                + (lighting ? '\n' + LIGHT_LABELS[illustration.lighting] + ' · 只演示原说明中的一类布光 / one stated lighting family\n' + resource.lighting_notes.zh + '\n' + resource.lighting_notes.en : '')
                + '\n此处场景和光影开关仅影响示意，不修改节点作用范围。 / Preview controls do not change the node scope.';
        };
    } else {
        const methodButtons = resource.methods.map((method, i) => button(`${i + 1}. ${DIAGRAM_LABELS[illustration.methods[i]]}`, () => {selected = i; draw();}));
        const play = button('播放示意 / Play', () => {
            if (play.disabled) return;
            if (playing) {pause(); return;}
            playing = true; play.textContent = '暂停 / Pause'; let previous, lastDraw = -Infinity;
            const tick = now => {
                if (!alive() || !playing || !root.isConnected) {dispose(); return;}
                if (document.hidden) {pause(); return;}
                if (previous !== undefined) progress = (progress + Math.min(now - previous, 80) / 6000) % 1;
                previous = now;
                if (now - lastDraw >= 65) {slider.value = String(Math.round(progress * 100)); draw(); lastDraw = now;}
                frame = requestAnimationFrame(tick);
            };
            frame = requestAnimationFrame(tick);
        });
        pause = () => {playing = false; if (frame) cancelAnimationFrame(frame); frame = 0; play.textContent = '播放示意 / Play';};
        document.addEventListener('visibilitychange', visibilityChanged);
        const slider = html('input', '', controls); slider.type = 'range'; slider.min = '0'; slider.max = '100'; slider.value = '50';
        slider.setAttribute('aria-label', '示意进度（非视频时长） / Illustration progress');
        slider.oninput = () => {if (alive()) {progress = clamp(Number(slider.value) / 100); draw();}};
        draw = () => {
            rightHost.replaceChildren();
            const code = illustration.methods[selected], method = resource.methods[selected];
            const animated = MOTION.has(code);
            if (!animated) pause();
            play.disabled = slider.disabled = !animated;
            play.textContent = playing ? '暂停 / Pause' : animated ? '播放示意 / Play' : '静态构图 / Static';
            leftTitle.textContent = '中性空间示意 / Neutral setup'; rightTitle.textContent = DIAGRAM_LABELS[code];
            methodButtons.forEach((b, i) => b.setAttribute('aria-pressed', String(i === selected)));
            if (!leftHost.children.length) stage(rootSVG(leftHost, leftTitle.textContent), 'fixed', .5);
            const svg = rootSVG(rightHost, rightTitle.textContent);
            (TIMELINES.has(code) ? timeline : stage)(svg, code, progress);
            svg.dataset.diagram = code;
            svg.dataset.progress = String(Math.round(progress * 100));
            explanation.textContent = method.text_zh + '\n' + method.text_en
                + (method.requires_cuts ? '\n需要允许切镜；固定单镜时实际增强会跳过此条。 / Requires cuts; skipped by the enhancer for a single shot.' : '')
                + '\n示意只解释该条中的一种拍法，不是电影剧照或完整导演风格。A/B、物件、箭头均为教学符号，不会加入提示词。\nOne method illustrated, not a film still or the entire creator style. Symbols never enter the prompt. Relative progress is not a duration limit.';
        };
    }
    draw();
    const tested = html('details', '', root); tested.style.cssText = 'margin:14px 0;padding:10px;border:1px solid #52616c;border-radius:8px';
    html('summary', '真实生成对比：未实测 / Real model comparison: not tested', tested);
    html('p', '目前没有此条目的 H3 / Seedance 实测样片。上方为原创矢量示意，不代表模型一定遵从。可使用同一内容分别运行 Off、仅颜色、仅导演、组合，记录模型/版本/参数与增强前后提示词；此面板不会发起生成或付费请求。', tested);
    html('p', 'No verified H3 / Seedance output is bundled for this entry. Compare Off / color / creator / combined using the same content and recorded settings. Browsing never starts inference.', tested);
    return dispose;
}
