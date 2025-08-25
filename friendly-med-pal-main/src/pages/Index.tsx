import { useState } from "react";
import Navigation from "@/components/ui/navigation";
import Dashboard from "@/components/Dashboard";
import PatientForm from "@/components/PatientForm";
import DrugForm from "@/components/DrugForm";
import DeliveryForm from "@/components/DeliveryForm";
import DeliveryHistory from "@/components/DeliveryHistory";

const Index = () => {
  const [activeTab, setActiveTab] = useState("dashboard");

  const renderContent = () => {
    switch (activeTab) {
      case "dashboard":
        return <Dashboard />;
      case "patients":
        return <PatientForm />;
      case "drugs":
        return <DrugForm />;
      case "deliveries":
        return <DeliveryForm />;
      case "history":
        return <DeliveryHistory />;
      default:
        return <Dashboard />;
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <Navigation activeTab={activeTab} onTabChange={setActiveTab} />
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {renderContent()}
      </main>
    </div>
  );
};

export default Index;
