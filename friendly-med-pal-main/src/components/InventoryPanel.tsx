import { useInventoryDrugs, useInventorySummary, useInventoryTransactions } from '@/api/hooks';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './ui/card';
import { ScrollArea } from './ui/scroll-area';
import { ArrowUpCircle, ArrowDownCircle, Database } from 'lucide-react';

function classNames(...c: (string|false|undefined)[]) { return c.filter(Boolean).join(' '); }

export default function InventoryPanel(){
  const { data: drugs } = useInventoryDrugs();
  const { data: summary } = useInventorySummary();
  const { data: txns } = useInventoryTransactions(200);

  // Merge summary metrics into drugs by id (simple map)
  const metrics = new Map(summary?.map(s=> [s.id, s]) || []);
  const rows = (drugs||[]).map(d=> ({...d, ...(metrics.get(d.id)||{})}));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold tracking-tight">Inventory</h2>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: inventory list (span 2 columns on large) */}
        <Card className="lg:col-span-2 overflow-hidden border-border/70">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2"><Database className="w-4 h-4"/> Stock Levels</CardTitle>
            <CardDescription>Current drug stock and reorder thresholds</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-muted/40 border-b border-border/60">
                  <tr className="text-xs uppercase text-muted-foreground">
                    <th className="px-3 py-2 text-left font-semibold">Drug</th>
                    <th className="px-3 py-2 text-left font-semibold">Dosage</th>
                    <th className="px-3 py-2 text-right font-semibold">Stock</th>
                    <th className="px-3 py-2 text-right font-semibold">Reorder</th>
                    <th className="px-3 py-2 text-right font-semibold">Pending</th>
                    <th className="px-3 py-2 text-right font-semibold">Days Supply</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map(r=>{
                    const low = (r.reorder_level ?? 0) > 0 && (r.stock ?? 0) <= r.reorder_level;
                    return (
                      <tr key={r.id} className={classNames('border-b border-border/50 hover:bg-muted/30', low && 'bg-destructive/5')}> 
                        <td className="px-3 py-2 font-medium whitespace-nowrap">{r.name}</td>
                        <td className="px-3 py-2 whitespace-nowrap text-muted-foreground">{r.dosage || '-'}</td>
                        <td className={classNames('px-3 py-2 text-right font-medium', low && 'text-destructive')}>{r.stock ?? 0}</td>
                        <td className="px-3 py-2 text-right text-muted-foreground">{r.reorder_level ?? 0}</td>
                        <td className="px-3 py-2 text-right text-muted-foreground">{r.pending_quantity ?? 0}</td>
                        <td className="px-3 py-2 text-right text-muted-foreground">{r.days_supply ?? '-'}</td>
                      </tr>
                    );
                  })}
                  {rows.length===0 && (
                    <tr><td colSpan={6} className="px-4 py-6 text-center text-muted-foreground text-sm">No drugs yet.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
        {/* Right: transactions */}
        <Card className="h-full flex flex-col border-border/70">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Recent Transactions</CardTitle>
            <CardDescription>Last {txns?.length || 0} adjustments</CardDescription>
          </CardHeader>
          <CardContent className="flex-1 p-0">
            <ScrollArea className="h-[480px]">
              <ul className="divide-y divide-border/50 text-sm">
                {(txns||[]).map(t=>{
                  const inc = t.delta > 0;
                  return (
                    <li key={t.id} className="px-3 py-2 flex items-start gap-2 hover:bg-muted/30">
                      <div className={classNames('mt-0.5 rounded-full p-1', inc ? 'bg-emerald-500/10 text-emerald-500' : 'bg-red-500/10 text-red-500')}>
                        {inc ? <ArrowUpCircle className="w-4 h-4"/> : <ArrowDownCircle className="w-4 h-4"/>}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2">
                          <span className={classNames('font-medium truncate', inc ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400')}>{inc? '+' : ''}{t.delta}</span>
                          <time className="text-xs text-muted-foreground whitespace-nowrap">{new Date(t.created_at).toLocaleDateString()} {new Date(t.created_at).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}</time>
                        </div>
                        <p className="text-xs text-muted-foreground truncate">{t.reason || 'adjustment'}</p>
                      </div>
                    </li>
                  );
                })}
                {(!txns || txns.length===0) && <li className="px-4 py-6 text-center text-muted-foreground text-xs">No transactions yet.</li>}
              </ul>
            </ScrollArea>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
