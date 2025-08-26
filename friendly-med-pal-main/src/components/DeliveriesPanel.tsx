import DeliveryForm from './DeliveryForm';
import { useDeliveries, usePatients, useDrugs } from '@/api/hooks';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Package } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

function statusBadge(status:string){
  switch(status){
    case 'delivered': return 'bg-medical-success text-white';
    case 'pending': return 'bg-medical-pending text-white';
    case 'missed': return 'bg-destructive text-destructive-foreground';
    default: return 'bg-muted text-muted-foreground';
  }
}

export default function DeliveriesPanel(){
  const deliveriesQ = useDeliveries();
  const patientsQ = usePatients();
  const drugsQ = useDrugs();
  const deliveries = deliveriesQ.data || [];
  const patients = new Map((patientsQ.data||[]).map(p=> [p.id,p]));
  const drugs = new Map((drugsQ.data||[]).map(d=> [d.id,d]));

  const pending = deliveries.filter(d=> d.status==='pending').length;
  const deliveredToday = deliveries.filter(d=> d.status==='delivered' && new Date(d.scheduled_for).toDateString() === new Date().toDateString()).length;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Total Deliveries</CardTitle><CardDescription>All records</CardDescription></CardHeader>
          <CardContent><div className="text-2xl font-bold">{deliveries.length}</div></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Pending</CardTitle><CardDescription>Awaiting action</CardDescription></CardHeader>
          <CardContent><div className="text-2xl font-bold">{pending}</div></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Delivered Today</CardTitle><CardDescription>Completed</CardDescription></CardHeader>
          <CardContent><div className="text-2xl font-bold">{deliveredToday}</div></CardContent>
        </Card>
        <Card className="bg-gradient-to-br from-medical-info/5 to-medical-info/10 border-medical-info/20">
          <CardContent className="h-full flex items-center gap-3 p-4">
            <div className="w-10 h-10 rounded-lg bg-medical-info/10 flex items-center justify-center"><Package className="w-5 h-5 text-medical-info"/></div>
            <p className="text-sm text-muted-foreground">Schedule, track and manage deliveries with real-time status updates.</p>
          </CardContent>
        </Card>
      </div>
      <div className="grid lg:grid-cols-5 gap-8 items-start">
        <div className="lg:col-span-2 space-y-4 sticky top-4">
          <DeliveryForm />
        </div>
        <div className="lg:col-span-3">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Recent Deliveries</CardTitle>
              <CardDescription>Latest scheduled and completed</CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <div className="max-h-[480px] overflow-auto rounded-b-lg">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Patient</TableHead>
                      <TableHead>Drug</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {deliveriesQ.isLoading && (
                      <TableRow><TableCell colSpan={4} className="text-center text-muted-foreground">Loading...</TableCell></TableRow>
                    )}
                    {!deliveriesQ.isLoading && deliveries.length===0 && (
                      <TableRow><TableCell colSpan={4} className="text-center text-muted-foreground">No deliveries yet</TableCell></TableRow>
                    )}
                    {deliveries.map(d=> (
                      <TableRow key={d.id} className="hover:bg-muted/40">
                        <TableCell className="whitespace-nowrap">{new Date(d.scheduled_for).toLocaleDateString()}</TableCell>
                        <TableCell>{patients.get(d.patient_id)?.name || `#${d.patient_id}`}</TableCell>
                        <TableCell>{drugs.get(d.drug_id)?.name || `#${d.drug_id}`}</TableCell>
                        <TableCell>
                          <Badge className={statusBadge(d.status)}>{d.status}</Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
