import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { usePatients, useDrugs, useAddDelivery } from "@/api/hooks";
import { Calendar } from "lucide-react";

// Types now come from hooks (simplified via inference)

const DeliveryForm = () => {
  const [formData, setFormData] = useState({
    patientId: "",
    drugId: "",
    deliveryDate: "",
    status: "pending",
  });
  const { toast } = useToast();
  const patientsQ = usePatients();
  const drugsQ = useDrugs();
  const addDelivery = useAddDelivery();
  const patients = patientsQ.data || [];
  const drugs = drugsQ.data || [];
  const isSubmitting = addDelivery.isPending;
  const isLoading = patientsQ.isLoading || drugsQ.isLoading;

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSelectChange = (name: string, value: string) => {
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await addDelivery.mutateAsync({
        patient_id: parseInt(formData.patientId),
        drug_id: parseInt(formData.drugId),
        scheduled_for: formData.deliveryDate,
        status: formData.status,
      });
      const patient = patients.find(p => p.id === parseInt(formData.patientId));
      const drug = drugs.find(d => d.id === parseInt(formData.drugId));
      toast({ title: 'Delivery Recorded', description: `${patient?.name} - ${drug?.name}` });
      setFormData({ patientId: "", drugId: "", deliveryDate: "", status: "pending" });
    } catch (e:any){
      toast({ title:'Record Failed', description: e?.message || 'Could not record delivery', variant:'destructive' });
    }
  };

  if (isLoading) {
    return (
      <Card className="max-w-md mx-auto">
        <CardContent className="p-6 space-y-4">
          <div className="h-4 w-2/3 bg-muted animate-pulse rounded" />
          <div className="h-4 w-1/2 bg-muted animate-pulse rounded" />
          <div className="h-10 w-full bg-muted animate-pulse rounded" />
          <div className="h-10 w-full bg-muted animate-pulse rounded" />
          <div className="h-10 w-full bg-muted animate-pulse rounded" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="max-w-md mx-auto">
      <CardHeader>
        <div className="flex items-center space-x-2">
          <Calendar className="w-5 h-5 text-primary" />
          <CardTitle>Record Drug Delivery</CardTitle>
        </div>
        <CardDescription>
          Schedule or record a drug delivery event
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="patient">Patient</Label>
            <Select
              value={formData.patientId}
              onValueChange={(value) => handleSelectChange("patientId", value)}
              required
            >
              <SelectTrigger>
                <SelectValue placeholder="Select a patient" />
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
          
          <div className="space-y-2">
            <Label htmlFor="drug">Drug</Label>
            <Select
              value={formData.drugId}
              onValueChange={(value) => handleSelectChange("drugId", value)}
              required
            >
              <SelectTrigger>
                <SelectValue placeholder="Select a drug" />
              </SelectTrigger>
              <SelectContent>
                {drugs.map((drug) => (
                  <SelectItem key={drug.id} value={drug.id.toString()}>
                    {drug.name}{drug.dosage ? ` - ${drug.dosage}`: ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          
          <div className="space-y-2">
            <Label htmlFor="deliveryDate">Delivery Date</Label>
            <Input
              id="deliveryDate"
              name="deliveryDate"
              type="date"
              value={formData.deliveryDate}
              onChange={handleInputChange}
              required
            />
          </div>
          
          <div className="space-y-2">
            <Label htmlFor="status">Status</Label>
            <Select
              value={formData.status}
              onValueChange={(value) => handleSelectChange("status", value)}
            >
              <SelectTrigger>
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
          
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? "Recording..." : "Record Delivery"}
          </Button>
          {addDelivery.isError && (
            <p className="text-xs text-destructive">{(addDelivery.error as any)?.message || 'Submission error'}</p>
          )}
        </form>
      </CardContent>
    </Card>
  );
};

export default DeliveryForm;