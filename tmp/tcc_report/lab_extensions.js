(() => {
  'use strict';
  const get = id => document.getElementById(id);
  const fmt = v => new Intl.NumberFormat('pt-BR', {minimumFractionDigits: 3, maximumFractionDigits: 3}).format(v);
  const ns = 'http://www.w3.org/2000/svg';
  function causal() {
    const t = Number(get('lab-origin').value);
    get('lab-origin-value').textContent = t;
    const svg = get('lab-causal-chart'); svg.replaceChildren();
    function node(tag, attrs, text) {
      const n = document.createElementNS(ns, tag);
      for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, String(v));
      if (text !== undefined) n.textContent = text;
      svg.append(n);
    }
    for (let i = 0; i < 30; i++) {
      node('rect', {x: 20 + i * 23, y: 50, width: 21, height: 35, rx: 3, fill: i < 20 ? '#197f70' : '#e6b45d'});
    }
    node('line', {x1: 478, x2: 478, y1: 40, y2: 95, stroke: '#182f34', 'stroke-width': 2});
    node('text', {x: 20, y: 34, fill: '#185f3a', 'font-size': 15}, '20 posições observadas');
    node('text', {x: 488, y: 34, fill: '#89500d', 'font-size': 15}, '10 alvos futuros');
    node('text', {x: 20, y: 118, fill: '#182f34', 'font-size': 14}, String(t - 19));
    node('text', {x: 467, y: 118, fill: '#182f34', 'font-size': 14, 'text-anchor': 'end'}, 't = ' + t);
    node('text', {x: 708, y: 118, fill: '#182f34', 'font-size': 14, 'text-anchor': 'end'}, String(t + 10));
    get('lab-causal-output').textContent = `Histórico: ${t - 19}..${t} (20 posições). Alvos: ${t + 1}..${t + 10} (10 posições). Os 19 pares históricos vão de ${t - 19}→${t - 18} até ${t - 1}→${t}. Último par permitido: ${t - 1}→${t}; par futuro proibido na entrada: ${t}→${t + 1}.`;
  }
  function bilinear() {
    const a = Number(get('lab-alpha').value), b = Number(get('lab-beta').value);
    const weights = [(1-a)*(1-b), a*(1-b), (1-a)*b, a*b];
    const unavailable = get('lab-invalid-corner').checked && weights[3] > 0;
    const out = get('lab-bilinear-output'); out.replaceChildren();
    const p = document.createElement('p'); p.textContent = `α = ${fmt(a)}; β = ${fmt(b)}. Pesos: ${weights.map(fmt).join('; ')}. Soma = ${fmt(weights.reduce((x,y)=>x+y,0))}.`;
    const result = document.createElement('strong');
    result.textContent = unavailable ? 'Amostra inválida: vizinho inválido com peso positivo. u/v ausentes; não substituir por zero.' : `Amostra válida: (u; v) = (${fmt(4*a)}; ${fmt(2*b)}) pixels por intervalo.`;
    out.append(p, result);
    if (get('lab-invalid-corner').checked && !unavailable) {
      const note = document.createElement('p'); note.textContent = 'O vizinho inválido tem peso zero e não contribui para a interpolação.'; out.append(note);
    }
  }
  get('lab-origin').addEventListener('input', causal);
  for (const id of ['lab-alpha','lab-beta','lab-invalid-corner']) get(id).addEventListener('input', bilinear);
  causal(); bilinear();
})();
