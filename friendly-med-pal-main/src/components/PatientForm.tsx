import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { User } from "lucide-react";

const PatientForm = () => {
  const [formData, setFormData] = useState({
    name: "",
    age: "",
    contact: "",
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { toast } = useToast();

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);

    try {
      // Simulate API call to backend
      const response = await fetch('/api/patients', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: formData.name,
          age: parseInt(formData.age),
          contact: formData.contact || null,
        }),
      });

      if (response.ok) {
        toast({
          title: "Patient Added Successfully",
          description: `${formData.name} has been added to the system.`,
        });
        setFormData({ name: "", age: "", contact: "" });
      } else {
        throw new Error('Failed to add patient');
      }
    } catch (error) {
      toast({
        title: "Error Adding Patient",
        description: "Please check your connection and try again.",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
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
          
          <Button
            type="submit"
            className="w-full"
            disabled={isSubmitting}
          >
            {isSubmitting ? "Adding Patient..." : "Add Patient"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
};

export default PatientForm;