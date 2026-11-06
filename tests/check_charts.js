const fs=require('fs'),vm=require('vm'),assert=require('assert'),echarts=require('../static/echarts.min.js');
const context={window:{},structuredClone};vm.createContext(context);vm.runInContext(fs.readFileSync('static/charts.js','utf8'),context);const editor=context.window.ChartEditor;
for(const type of Object.keys(editor.types)){
 const c=editor.defaults('Accreditation <progress>');c.type=type;c.headers=['Period','Open','Close','Low','High'];c.rows=[['A',10,14,8,18],['B',12,15,9,20],['C',11,13,7,19]];
 const chart=echarts.init(null,null,{renderer:'svg',ssr:true,width:1000,height:650});
 try{chart.setOption(editor.option(c));const svg=chart.renderToSVGString();assert(svg.includes('<svg'));assert(!svg.includes('NaN'),type+' has invalid coordinates');assert(svg.length>1000,type+' empty');}finally{chart.dispose();}
}
const invalid=editor.defaults('Bad stock');invalid.type='stock';assert.throws(()=>editor.option(invalid),/four numeric/);
console.log('All 22 chart types rendered to SVG without invalid coordinates; stock validation passed.');
