import PatientForm from './PatientForm';
import { usePatients } from '@/api/hooks';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Users } from 'lucide-react';

export default function PatientsPanel(){
  const patientsQ = usePatients();
  const patients = patientsQ.data || [];
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Patients</CardTitle><CardDescription>Total registered</CardDescription></CardHeader>
          <CardContent><div className="text-2xl font-bold">{patients.length}</div></CardContent>
        </Card>
        <Card className="sm:col-span-2 lg:col-span-3 bg-gradient-to-br from-primary/5 to-primary/10 border-primary/20">
          <CardContent className="h-full flex items-center gap-3 p-4">
            <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center"><Users className="w-5 h-5 text-primary"/></div>
            <p className="text-sm text-muted-foreground">Add new patients and review existing records. Future enhancements: edit, archive, activity timeline.</p>
          </CardContent>
        </Card>
      </div>
      <div className="grid lg:grid-cols-5 gap-8 items-start">
        <div className="lg:col-span-2 xl:col-span-2 space-y-4 sticky top-4">
          <PatientForm />
        </div>
        <div className="lg:col-span-3 xl:col-span-3">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Patient Directory</CardTitle>
              <CardDescription>All patients currently in system</CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <div className="max-h-[480px] overflow-auto rounded-b-lg">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-12">ID</TableHead>
                      <TableHead>Name</TableHead>
                      <TableHead>Age</TableHead>
                      <TableHead>Contact</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {patientsQ.isLoading && (
                      <TableRow><TableCell colSpan={4} className="text-center text-muted-foreground">Loading...</TableCell></TableRow>
                    )}
                    {!patientsQ.isLoading && patients.length===0 && (
                      <TableRow><TableCell colSpan={4} className="text-center text-muted-foreground">No patients yet</TableCell></TableRow>
                    )}
                    {patients.map(p=> (
                      <TableRow key={p.id} className="hover:bg-muted/40">
                        <TableCell>{p.id}</TableCell>
                        <TableCell className="font-medium">{p.name}</TableCell>
                        <TableCell>{p.age ?? '-'}</TableCell>
                        <TableCell className="text-xs break-all max-w-[160px]">{p.contact || <span className="text-muted-foreground">—</span>}</TableCell>
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
