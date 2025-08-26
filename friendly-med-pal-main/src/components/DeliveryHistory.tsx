import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { usePatients, useDeliveries, useUpdateDeliveryStatus, useDrugs } from "@/api/hooks";
import { FileText, Calendar, Pill } from "lucide-react";

// Types inferred from hooks; legacy interfaces removed

const DeliveryHistory = () => {
  const [selectedPatient, setSelectedPatient] = useState("");
  const { toast } = useToast();
  const patientsQ = usePatients();
  const drugsQ = useDrugs();
  const deliveriesQ = useDeliveries();
  const updateStatus = useUpdateDeliveryStatus();
  const patients = patientsQ.data || [];
  const allDeliveries = deliveriesQ.data || [];
  const deliveries = selectedPatient ? allDeliveries.filter(d=> String(d.patient_id)===selectedPatient) : allDeliveries;
  const drugs = drugsQ.data || [];
  const isLoading = patientsQ.isLoading || deliveriesQ.isLoading;

  const updateDeliveryStatus = async (id:number, status:string)=>{
    try { await updateStatus.mutateAsync({id,status}); toast({ title:'Status Updated', description: status }); }
    catch(e:any){ toast({ title:'Update Failed', description: e?.message || 'Could not update', variant:'destructive' }); }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "delivered":
        return "bg-medical-success text-white";
      case "pending":
        return "bg-medical-pending text-white";
      case "missed":
        return "bg-destructive text-destructive-foreground";
      case "cancelled":
        return "bg-muted text-muted-foreground";
      default:
        return "bg-secondary text-secondary-foreground";
    }
  };

  return (
    <Card className="max-w-4xl mx-auto">
      <CardHeader>
        <div className="flex items-center space-x-2">
          <FileText className="w-5 h-5 text-primary" />
          <CardTitle>Delivery History</CardTitle>
        </div>
        <CardDescription>
          View and manage delivery records for patients
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-2">
          <Label htmlFor="patient-select">Select Patient</Label>
          <Select
            value={selectedPatient}
            onValueChange={(value) => setSelectedPatient(value)}
          >
            <SelectTrigger>
              <SelectValue placeholder="Choose a patient to view history" />
            </SelectTrigger>
            <SelectContent>
              {patients.map((patient) => (
                <SelectItem key={patient.id} value={patient.id.toString()}>
                  {patient.name} (Age: {patient.age})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {isLoading && (
          <div className="text-center text-muted-foreground py-8">
            Loading delivery history...
          </div>
        )}

        {!isLoading && selectedPatient && deliveries.length === 0 && (
          <div className="text-center text-muted-foreground py-8">
            No delivery records found for this patient.
          </div>
        )}

        {!isLoading && deliveries.length > 0 && (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">
              Delivery Records ({deliveries.length})
            </h3>
            
            <div className="space-y-3">
              {deliveries.map((delivery) => {
                const drug = drugs.find(d=> d.id === delivery.drug_id);
                return (
                <Card key={delivery.id} className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="space-y-2">
                      <div className="flex items-center space-x-4">
                        <div className="flex items-center space-x-2">
                          <Pill className="w-4 h-4 text-muted-foreground" />
                          <span className="font-medium">{drug?.name || `Drug #${delivery.drug_id}`}</span>
                        </div>
                        <div className="flex items-center space-x-2">
                          <Calendar className="w-4 h-4 text-muted-foreground" />
                          <span className="text-sm text-muted-foreground">
                            {new Date(delivery.scheduled_for).toLocaleDateString()}
                          </span>
                        </div>
                      </div>
                      
                      {delivery.quantity != null && (
                        <div className="text-sm text-muted-foreground">
                          Quantity: {delivery.quantity}
                        </div>
                      )}
                    </div>
                    
                    <div className="flex items-center space-x-3">
                      <Badge className={getStatusColor(delivery.status)}>
                        {delivery.status}
                      </Badge>
                      
                      <Select
                        value={delivery.status}
                        onValueChange={(value) => updateDeliveryStatus(delivery.id, value)}
                      >
                        <SelectTrigger className="w-32">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="pending">Pending</SelectItem>
                          <SelectItem value="delivered">Delivered</SelectItem>
                          <SelectItem value="missed">Missed</SelectItem>
                          <SelectItem value="cancelled">Cancelled</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </Card>
              );})}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default DeliveryHistory;