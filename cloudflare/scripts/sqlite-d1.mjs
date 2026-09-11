/** Offline D1 API test double backed by real SQLite. NOT Cloudflare/workerd. */
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
export class LocalD1 {
  constructor(filename=':memory:'){
    this.sqlite=new DatabaseSync(filename);this.sqlite.exec('PRAGMA foreign_keys=ON');
    this.sqlite.exec(readFileSync(new URL('../migrations/0001_cloudflare.sql',import.meta.url),'utf8'));
    this.queries=0;this.beforeBatch=null;
  }
  prepare(sql){
    const owner=this;
    function bound(args){
      function execute(){
        owner.queries++;
        const stmt=owner.sqlite.prepare(sql);
        if(stmt.columns().length){return {success:true,results:stmt.all(...args),meta:{changes:0}};}
        const meta=stmt.run(...args);return {success:true,results:[],meta:{changes:Number(meta.changes)}};
      }
      return {bind:(...values)=>bound(values),
        async first(column){owner.queries++;const r=owner.sqlite.prepare(sql).get(...args)||null;return column?r?.[column]??null:r;},
        async all(){return execute();},async run(){return execute();},_execute:execute};
    }
    return bound([]);
  }
  async batch(statements){
    if(this.beforeBatch)await this.beforeBatch();
    this.sqlite.exec('BEGIN');
    try{const values=statements.map(s=>s._execute());this.sqlite.exec('COMMIT');return values;}
    catch(e){this.sqlite.exec('ROLLBACK');throw e;}
  }
  close(){this.sqlite.close();}
}
