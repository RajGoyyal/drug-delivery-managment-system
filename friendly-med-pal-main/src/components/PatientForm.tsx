import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useAddPatient } from "@/api/hooks";
import { User } from "lucide-react";

const PatientForm = () => {
  const [formData, setFormData] = useState({
    name: "",
    age: "",
    contact: "",
  });
  const { toast } = useToast();
  const addPatient = useAddPatient();
  const isSubmitting = addPatient.isPending;

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await addPatient.mutateAsync({
        name: formData.name,
        age: parseInt(formData.age),
        contact: formData.contact || undefined,
      });
      toast({
        title: "Patient Added",
        description: `${formData.name} has been added.`,
      });
      setFormData({ name: "", age: "", contact: "" });
    } catch (error: any) {
      toast({
        title: "Add Failed",
        description: error?.message || 'Could not add patient',
        variant: "destructive",
      });
    }
  };

  return (
    <Card className="max-w-md mx-auto">
      <CardHeader>
        <div className="flex items-center space-x-2">
          <User className="w-5 h-5 text-primary" />
          <CardTitle>Add New Patient</CardTitle>
        </div>
        <CardDescription>
          Register a new patient in the delivery system
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">Full Name</Label>
            <Input
              id="name"
              name="name"
              type="text"
              placeholder="Enter patient's full name"
              value={formData.name}
              onChange={handleInputChange}
              required
            />
          </div>
          
          <div className="space-y-2">
            <Label htmlFor="age">Age</Label>
            <Input
              id="age"
              name="age"
              type="number"
              placeholder="Enter age"
              min="0"
              max="150"
              value={formData.age}
              onChange={handleInputChange}
              required
            />
          </div>
          
          <div className="space-y-2">
            <Label htmlFor="contact">Contact Information</Label>
            <Input
              id="contact"
              name="contact"
              type="text"
              placeholder="Email or phone (optional)"
              value={formData.contact}
              onChange={handleInputChange}
            />
          </div>
          
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? "Adding..." : "Add Patient"}
          </Button>
          {addPatient.isError && (
            <p className="text-xs text-destructive">{(addPatient.error as any)?.message || 'Submission error'}</p>
          )}
        </form>
      </CardContent>
    </Card>
  );
};

export default PatientForm;