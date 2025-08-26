import DrugForm from './DrugForm';
import { useDrugs } from '@/api/hooks';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Pill } from 'lucide-react';

export default function DrugsPanel(){
  const drugsQ = useDrugs();
  const drugs = drugsQ.data || [];
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Drugs</CardTitle><CardDescription>In catalog</CardDescription></CardHeader>
          <CardContent><div className="text-2xl font-bold">{drugs.length}</div></CardContent>
        </Card>
        <Card className="sm:col-span-2 lg:col-span-3 bg-gradient-to-br from-medical-accent/5 to-medical-accent/10 border-medical-accent/20">
          <CardContent className="h-full flex items-center gap-3 p-4">
            <div className="w-10 h-10 rounded-lg bg-medical-accent/10 flex items-center justify-center"><Pill className="w-5 h-5 text-medical-accent"/></div>
            <p className="text-sm text-muted-foreground">Maintain the drug catalog. Future: stock levels, reorder alerts, classification tags.</p>
          </CardContent>
        </Card>
      </div>
      <div className="grid lg:grid-cols-5 gap-8 items-start">
        <div className="lg:col-span-2 space-y-4 sticky top-4">
          <DrugForm />
        </div>
        <div className="lg:col-span-3">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Drug Catalog</CardTitle>
              <CardDescription>All registered medications</CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <div className="max-h-[480px] overflow-auto rounded-b-lg">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-12">ID</TableHead>
                      <TableHead>Name</TableHead>
                      <TableHead>Dosage</TableHead>
                      <TableHead>Frequency</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {drugsQ.isLoading && (
                      <TableRow><TableCell colSpan={4} className="text-center text-muted-foreground">Loading...</TableCell></TableRow>
                    )}
                    {!drugsQ.isLoading && drugs.length===0 && (
                      <TableRow><TableCell colSpan={4} className="text-center text-muted-foreground">No drugs yet</TableCell></TableRow>
                    )}
                    {drugs.map(d=> (
                      <TableRow key={d.id} className="hover:bg-muted/40">
                        <TableCell>{d.id}</TableCell>
                        <TableCell className="font-medium">{d.name}</TableCell>
                        <TableCell>{d.dosage || '-'}</TableCell>
                        <TableCell>{(d as any).frequency || '-'}</TableCell>
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
