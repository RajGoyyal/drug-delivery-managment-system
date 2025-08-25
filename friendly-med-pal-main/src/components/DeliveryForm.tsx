import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { Calendar } from "lucide-react";

interface Patient {
  id: number;
  name: string;
  age: number;
  contact: string;
}

interface Drug {
  id: number;
  name: string;
  dosage: string;
  frequency: string;
}

const DeliveryForm = () => {
  const [formData, setFormData] = useState({
    patientId: "",
    drugId: "",
    deliveryDate: "",
    status: "pending",
  });
  const [patients, setPatients] = useState<Patient[]>([]);
  const [drugs, setDrugs] = useState<Drug[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const { toast } = useToast();

  useEffect(() => {
    // Fetch patients and drugs for the select dropdowns
    const fetchData = async () => {
      try {
        const [patientsRes, drugsRes] = await Promise.all([
          fetch('/api/patients'),
          fetch('/api/drugs'),
        ]);

        if (patientsRes.ok && drugsRes.ok) {
          setPatients(await patientsRes.json());
          setDrugs(await drugsRes.json());
        }
      } catch (error) {
        console.log("Mock data loaded for demo");
        // Mock data for demo
        setPatients([
          { id: 1, name: "Alice Johnson", age: 42, contact: "alice@example.com" },
          { id: 2, name: "Bob Smith", age: 65, contact: "bob@example.com" },
        ]);
        setDrugs([
          { id: 1, name: "Amoxicillin", dosage: "500 mg", frequency: "2x/day" },
          { id: 2, name: "Ibuprofen", dosage: "200 mg", frequency: "3x/day" },
        ]);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSelectChange = (name: string, value: string) => {
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);

    try {
      const response = await fetch('/api/deliveries', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          patient_id: parseInt(formData.patientId),
          drug_id: parseInt(formData.drugId),
          delivery_date: formData.deliveryDate,
          status: formData.status,
        }),
      });

      if (response.ok) {
        const patient = patients.find(p => p.id === parseInt(formData.patientId));
        const drug = drugs.find(d => d.id === parseInt(formData.drugId));
        
        toast({
          title: "Delivery Recorded",
          description: `Delivery scheduled for ${patient?.name} - ${drug?.name}`,
        });
        setFormData({ patientId: "", drugId: "", deliveryDate: "", status: "pending" });
      } else {
        throw new Error('Failed to record delivery');
      }
    } catch (error) {
      toast({
        title: "Error Recording Delivery",
        description: "Please check your connection and try again.",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <Card className="max-w-md mx-auto">
        <CardContent className="p-6">
          <div className="text-center text-muted-foreground">Loading patients and drugs...</div>
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
                    {drug.name} - {drug.dosage} ({drug.frequency})
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
          
          <Button
            type="submit"
            className="w-full"
            disabled={isSubmitting}
          >
            {isSubmitting ? "Recording Delivery..." : "Record Delivery"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
};

export default DeliveryForm;