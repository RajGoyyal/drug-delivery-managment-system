import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { FileText, Calendar, Pill, User } from "lucide-react";

interface Patient {
  id: number;
  name: string;
  age: number;
  contact: string;
}

interface DeliveryRecord {
  id: number;
  patient_id: number;
  patient_name: string;
  drug_id: number;
  drug_name: string;
  dosage: string;
  frequency: string;
  delivery_date: string;
  status: string;
}

const DeliveryHistory = () => {
  const [selectedPatient, setSelectedPatient] = useState("");
  const [patients, setPatients] = useState<Patient[]>([]);
  const [deliveries, setDeliveries] = useState<DeliveryRecord[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    // Fetch patients for the dropdown
    const fetchPatients = async () => {
      try {
        const response = await fetch('/api/patients');
        if (response.ok) {
          setPatients(await response.json());
        }
      } catch (error) {
        // Mock data for demo
        setPatients([
          { id: 1, name: "Alice Johnson", age: 42, contact: "alice@example.com" },
          { id: 2, name: "Bob Smith", age: 65, contact: "bob@example.com" },
        ]);
      }
    };

    fetchPatients();
  }, []);

  const fetchDeliveryHistory = async (patientId: string) => {
    setIsLoading(true);
    try {
      const response = await fetch(`/api/deliveries/patient/${patientId}`);
      if (response.ok) {
        setDeliveries(await response.json());
      } else {
        throw new Error('Failed to fetch delivery history');
      }
    } catch (error) {
      // Mock data for demo
      const mockDeliveries: DeliveryRecord[] = [
        {
          id: 1,
          patient_id: parseInt(patientId),
          patient_name: "Alice Johnson",
          drug_id: 1,
          drug_name: "Amoxicillin",
          dosage: "500 mg",
          frequency: "2x/day",
          delivery_date: "2024-12-20",
          status: "delivered"
        },
        {
          id: 2,
          patient_id: parseInt(patientId),
          patient_name: "Alice Johnson",
          drug_id: 2,
          drug_name: "Ibuprofen",
          dosage: "200 mg",
          frequency: "3x/day",
          delivery_date: "2024-12-22",
          status: "pending"
        }
      ];
      setDeliveries(mockDeliveries);
      
      toast({
        title: "Demo Mode",
        description: "Showing mock delivery data for demonstration.",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const updateDeliveryStatus = async (deliveryId: number, newStatus: string) => {
    try {
      const response = await fetch(`/api/deliveries/${deliveryId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      });

      if (response.ok) {
        setDeliveries(prev => 
          prev.map(delivery => 
            delivery.id === deliveryId 
              ? { ...delivery, status: newStatus }
              : delivery
          )
        );
        toast({
          title: "Status Updated",
          description: `Delivery status changed to ${newStatus}`,
        });
      } else {
        throw new Error('Failed to update status');
      }
    } catch (error) {
      // For demo purposes, update locally
      setDeliveries(prev => 
        prev.map(delivery => 
          delivery.id === deliveryId 
            ? { ...delivery, status: newStatus }
            : delivery
        )
      );
      toast({
        title: "Status Updated (Demo)",
        description: `Delivery status changed to ${newStatus}`,
      });
    }
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
            onValueChange={(value) => {
              setSelectedPatient(value);
              fetchDeliveryHistory(value);
            }}
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
              {deliveries.map((delivery) => (
                <Card key={delivery.id} className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="space-y-2">
                      <div className="flex items-center space-x-4">
                        <div className="flex items-center space-x-2">
                          <Pill className="w-4 h-4 text-muted-foreground" />
                          <span className="font-medium">{delivery.drug_name}</span>
                        </div>
                        <div className="flex items-center space-x-2">
                          <Calendar className="w-4 h-4 text-muted-foreground" />
                          <span className="text-sm text-muted-foreground">
                            {new Date(delivery.delivery_date).toLocaleDateString()}
                          </span>
                        </div>
                      </div>
                      
                      <div className="text-sm text-muted-foreground">
                        Dosage: {delivery.dosage} • Frequency: {delivery.frequency}
                      </div>
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
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default DeliveryHistory;