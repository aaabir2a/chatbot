import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { AppLayout } from "./components/Layout";
import { Spinner } from "./components/ui";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import Chatbots from "./pages/Chatbots";
import LiveChats from "./pages/LiveChats";
import ChatbotLayout from "./pages/chatbot/ChatbotLayout";
import ConfigPage from "./pages/chatbot/Config";
import DocumentsPage from "./pages/chatbot/Documents";
import ApiKeysPage from "./pages/chatbot/ApiKeys";
import UsagePage from "./pages/chatbot/Usage";
import TestChatPage from "./pages/chatbot/TestChat";

function Protected({ children }: { children: JSX.Element }) {
  const { org, loading } = useAuth();
  if (loading) return <Spinner />;
  return org ? children : <Navigate to="/login" replace />;
}

export default function App() {
  const { org, loading } = useAuth();

  return (
    <Routes>
      <Route
        path="/login"
        element={loading ? <Spinner /> : org ? <Navigate to="/" replace /> : <Login />}
      />
      <Route
        path="/signup"
        element={loading ? <Spinner /> : org ? <Navigate to="/" replace /> : <Signup />}
      />

      <Route
        element={
          <Protected>
            <AppLayout />
          </Protected>
        }
      >
        <Route path="/" element={<Chatbots />} />
        <Route path="/live" element={<LiveChats />} />
        <Route path="/chatbots/:id" element={<ChatbotLayout />}>
          <Route index element={<Navigate to="config" replace />} />
          <Route path="config" element={<ConfigPage />} />
          <Route path="documents" element={<DocumentsPage />} />
          <Route path="keys" element={<ApiKeysPage />} />
          <Route path="usage" element={<UsagePage />} />
          <Route path="chat" element={<TestChatPage />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
