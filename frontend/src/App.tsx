import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { 
  TrendingUp, 
  TrendingDown, 
  ArrowUpRight, 
  DollarSign, 
  UploadCloud, 
  AlertCircle, 
  ChevronRight, 
  Plus, 
  Search, 
  Edit3, 
  Check, 
  Trash2, 
  Lock, 
  Sparkles, 
  Settings, 
  Calendar,
  X,
  CreditCard,
  FileText
} from 'lucide-react';
import { 
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, 
  PieChart, Pie, Cell, Legend, LineChart, Line 
} from 'recharts';

// Set default axios base URL for simple dev mode proxying
axios.defaults.withCredentials = true;

// Predefined Categories
const CATEGORIES = [
  "Food",
  "Shopping",
  "Bills",
  "Entertainment",
  "Travel",
  "Healthcare",
  "Subscriptions",
  "Transfers",
  "Miscellaneous"
];

const CATEGORY_COLORS = {
  Food: "#f59e0b",         // Amber
  Shopping: "#ec4899",     // Pink
  Bills: "#3b82f6",        // Blue
  Entertainment: "#8b5cf6",// Violet
  Travel: "#06b6d4",       // Cyan
  Healthcare: "#10b981",   // Emerald
  Subscriptions: "#6366f1",// Indigo
  Transfers: "#14b8a6",    // Teal
  Miscellaneous: "#6b7280" // Gray
};

export default function App() {
  // Auth state
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(true);
  const [passwordRequired, setPasswordRequired] = useState<boolean>(false);
  const [password, setPassword] = useState<string>('');
  const [authError, setAuthError] = useState<string>('');

  // Dashboard active tab
  const [activeTab, setActiveTab] = useState<'dashboard' | 'transactions' | 'rules'>('dashboard');

  // Transactions lists & Filters
  const [transactions, setTransactions] = useState<any[]>([]);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedCategoryFilter, setSelectedCategoryFilter] = useState<string>('');
  const [selectedTypeFilter, setSelectedTypeFilter] = useState<string>('');
  
  // Dashboard Aggregates state
  const [totals, setTotals] = useState({ income: 0, expense: 0, net_savings: 0 });
  const [categoryChart, setCategoryChart] = useState<any[]>([]);
  const [cashflowChart, setCashflowChart] = useState<any[]>([]);
  const [predictions, setPredictions] = useState<any>({
    projected_spend: 0,
    projected_savings: 0,
    savings_change_pct: 0,
    next_month_predicted_spend: 0,
    next_month_predicted_savings: 0,
    forecast_chart: []
  });
  const [insights, setInsights] = useState<any[]>([]);

  // Rules list
  const [rules, setRules] = useState<any[]>([]);
  const [newRulePattern, setNewRulePattern] = useState<string>('');
  const [newRuleCategory, setNewRuleCategory] = useState<string>('Food');

  // Interactive dialogs/modals
  const [uploading, setUploading] = useState<boolean>(false);
  const [uploadSuccess, setUploadSuccess] = useState<string>('');
  const [uploadError, setUploadError] = useState<string>('');
  
  // CSV Mapping schema selector
  const [mappingRequired, setMappingRequired] = useState<boolean>(false);
  const [mappingColumns, setMappingColumns] = useState<string[]>([]);
  const [mappingSampleRows, setMappingSampleRows] = useState<any[]>([]);
  const [mappingFile, setMappingFile] = useState<File | null>(null);
  const [mappingConfig, setMappingConfig] = useState({
    date: '',
    description: '',
    amount: '',
    debit: '',
    credit: '',
    type: ''
  });

  // Manual Transaction Quick-Add
  const [quickAddQuery, setQuickAddQuery] = useState<string>('');
  const [quickAddLoading, setQuickAddLoading] = useState<boolean>(false);
  
  // Traditional Structured Add dialog
  const [showAddModal, setShowAddModal] = useState<boolean>(false);
  const [newTx, setNewTx] = useState({
    date: new Date().toISOString().split('T')[0],
    raw_description: '',
    amount: '',
    type: 'debit',
    category: 'Food'
  });

  // Inline edits
  const [editingTxId, setEditingTxId] = useState<number | null>(null);
  const [editingCategory, setEditingCategory] = useState<string>('');

  const fileInputRef = useRef<HTMLInputElement>(null);

  // 1. Initial Authentication Check
  useEffect(() => {
    checkAuth();
  }, []);

  // 2. Fetch dashboard, transactions, and rules if authenticated
  useEffect(() => {
    if (isAuthenticated) {
      fetchDashboard();
      fetchTransactions();
      fetchRules();
    }
  }, [isAuthenticated, selectedCategoryFilter, selectedTypeFilter, searchQuery]);

  const checkAuth = async () => {
    try {
      const res = await axios.get('/api/auth/check');
      setIsAuthenticated(res.data.authenticated);
      setPasswordRequired(res.data.password_required);
    } catch (err) {
      // Default to unauthenticated if API fails
      setIsAuthenticated(false);
      setPasswordRequired(true);
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError('');
    try {
      const res = await axios.post('/api/auth/login', { password });
      if (res.data.status === 'success' || res.status === 200) {
        setIsAuthenticated(true);
      }
    } catch (err: any) {
      setAuthError(err.response?.data?.detail || 'Incorrect password');
    }
  };

  const handleLogout = async () => {
    try {
      await axios.post('/api/auth/logout');
      setIsAuthenticated(false);
      checkAuth();
    } catch (err) {}
  };

  const fetchDashboard = async () => {
    try {
      const res = await axios.get('/api/dashboard');
      setTotals(res.data.totals);
      setCategoryChart(res.data.category_chart);
      setCashflowChart(res.data.cashflow_chart);
      setPredictions(res.data.predictions);
      setInsights(res.data.insights);
    } catch (err) {}
  };

  const fetchTransactions = async () => {
    try {
      const res = await axios.get('/api/transactions', {
        params: {
          category: selectedCategoryFilter || undefined,
          type: selectedTypeFilter || undefined,
          search: searchQuery || undefined,
          limit: 150
        }
      });
      setTransactions(res.data);
    } catch (err) {}
  };

  const fetchRules = async () => {
    try {
      const res = await axios.get('/api/rules');
      setRules(res.data);
    } catch (err) {}
  };

  // 3. Statement file uploads
  const handleFileUpload = async (file: File) => {
    setUploading(true);
    setUploadError('');
    setUploadSuccess('');
    setMappingRequired(false);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await axios.post('/api/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      if (res.data.requires_mapping) {
        setMappingColumns(res.data.columns);
        setMappingSampleRows(res.data.sample_rows);
        setMappingFile(file);
        setMappingRequired(true);
        // Pre-fill initial mapper fields if columns match typical names
        const cols = res.data.columns.map((c: string) => c.toLowerCase());
        const findCol = (keys: string[]) => res.data.columns.find((c: string) => keys.some(k => c.toLowerCase().includes(k))) || '';
        setMappingConfig({
          date: findCol(['date', 'tx date', 'value']),
          description: findCol(['desc', 'particular', 'narration', 'detail', 'payee', 'merchant']),
          amount: findCol(['amount', 'value']),
          debit: findCol(['debit', 'withdrawal']),
          credit: findCol(['credit', 'deposit']),
          type: findCol(['type', 'dr/cr'])
        });
      } else {
        setUploadSuccess(`Successfully imported ${res.data.imported_count} transactions!`);
        fetchDashboard();
        fetchTransactions();
      }
    } catch (err: any) {
      setUploadError(err.response?.data?.detail || 'Failed to parse statement.');
    } finally {
      setUploading(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  };

  const submitCustomMapping = async () => {
    if (!mappingFile) return;
    setUploading(true);
    setUploadError('');

    const formData = new FormData();
    formData.append('file', mappingFile);
    formData.append('mapping_json', JSON.stringify(mappingConfig));

    try {
      const res = await axios.post('/api/upload/map', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setUploadSuccess(`Successfully imported ${res.data.imported_count} transactions!`);
      setMappingRequired(false);
      setMappingFile(null);
      fetchDashboard();
      fetchTransactions();
    } catch (err: any) {
      setUploadError(err.response?.data?.detail || 'Mapping failed.');
    } finally {
      setUploading(false);
    }
  };

  // 4. Quick NLP Add transaction
  const handleQuickAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!quickAddQuery.trim()) return;
    setQuickAddLoading(true);
    try {
      await axios.post('/api/transactions/quick-add', { query: quickAddQuery });
      setQuickAddQuery('');
      fetchDashboard();
      fetchTransactions();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Could not parse query. Use format like "₹250 groceries"');
    } finally {
      setQuickAddLoading(false);
    }
  };

  // 5. Structured manual addition
  const handleAddTx = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await axios.post('/api/transactions', {
        ...newTx,
        amount: parseFloat(newTx.amount) || 0
      });
      setNewTx({
        date: new Date().toISOString().split('T')[0],
        raw_description: '',
        amount: '',
        type: 'debit',
        category: 'Food'
      });
      setShowAddModal(false);
      fetchDashboard();
      fetchTransactions();
    } catch (err) {}
  };

  // 6. Category Override (inline editing triggers ML retrain)
  const saveCategoryOverride = async (txId: number) => {
    try {
      await axios.patch(`/api/transactions/${txId}`, { category: editingCategory });
      setEditingTxId(null);
      fetchDashboard();
      fetchTransactions();
    } catch (err) {}
  };

  // 7. Rules management
  const handleAddRule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRulePattern.trim()) return;
    try {
      await axios.post('/api/rules', {
        pattern: newRulePattern,
        target_category: newRuleCategory
      });
      setNewRulePattern('');
      fetchRules();
      // Re-run parsing analysis
      fetchDashboard();
      fetchTransactions();
    } catch (err) {}
  };

  const handleDeleteRule = async (id: number) => {
    try {
      await axios.delete(`/api/rules/${id}`);
      fetchRules();
    } catch (err) {}
  };

  // Render Lock Screen if Unauthenticated
  if (!isAuthenticated && passwordRequired) {
    return (
      <div className="min-h-screen bg-stone-50 flex items-center justify-center p-6 select-none font-sans">
        <div className="w-full max-w-md bg-white border border-stone-200 shadow-premium rounded-2xl p-8 space-y-6">
          <div className="text-center space-y-2">
            <div className="w-12 h-12 bg-neutral-900 rounded-xl flex items-center justify-center mx-auto text-white">
              <Lock className="w-5 h-5" />
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-neutral-900 font-sans">Ledgr Lockscreen</h1>
            <p className="text-sm text-neutral-500 font-sans">Please enter your Master Password to access insights.</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-4 font-sans">
            <div>
              <label className="block text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-2 font-sans">Master Password</label>
              <input 
                type="password" 
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full px-4 py-3 bg-stone-50 border border-neutral-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-neutral-900 focus:bg-white text-sm transition-all"
                required
              />
            </div>
            
            {authError && (
              <div className="flex items-center gap-2 text-xs text-rose-600 bg-rose-50 border border-rose-100 p-3 rounded-lg">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{authError}</span>
              </div>
            )}

            <button 
              type="submit"
              className="w-full py-3 bg-neutral-900 hover:bg-neutral-800 text-white rounded-xl font-medium text-sm transition-all hover:shadow-premium"
            >
              Access Ledgr
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-stone-50 flex flex-col font-sans text-neutral-800">
      
      {/* Header bar */}
      <header className="sticky top-0 bg-white/80 backdrop-blur-md border-b border-stone-200/80 z-20 transition-all duration-300">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-neutral-950 rounded-lg flex items-center justify-center text-white font-bold text-sm">
              L
            </div>
            <span className="font-bold text-lg tracking-tight text-neutral-900">Ledgr</span>
            <span className="text-[10px] uppercase font-bold tracking-widest bg-emerald-50 text-emerald-700 border border-emerald-100 px-2 py-0.5 rounded-full flex items-center gap-1 font-sans">
              <Sparkles className="w-2.5 h-2.5" /> AI Engine Active
            </span>
          </div>

          <div className="flex items-center gap-6">
            <nav className="flex gap-1 text-sm font-medium">
              <button 
                onClick={() => setActiveTab('dashboard')}
                className={`px-3 py-1.5 rounded-lg transition-all ${activeTab === 'dashboard' ? 'bg-neutral-100 text-neutral-900 font-semibold' : 'text-neutral-500 hover:text-neutral-900'}`}
              >
                Dashboard
              </button>
              <button 
                onClick={() => setActiveTab('transactions')}
                className={`px-3 py-1.5 rounded-lg transition-all ${activeTab === 'transactions' ? 'bg-neutral-100 text-neutral-900 font-semibold' : 'text-neutral-500 hover:text-neutral-900'}`}
              >
                Transactions
              </button>
              <button 
                onClick={() => setActiveTab('rules')}
                className={`px-3 py-1.5 rounded-lg transition-all ${activeTab === 'rules' ? 'bg-neutral-100 text-neutral-900 font-semibold' : 'text-neutral-500 hover:text-neutral-900'}`}
              >
                Rules
              </button>
            </nav>

            <button 
              onClick={handleLogout}
              className="text-xs font-medium text-neutral-400 hover:text-neutral-700 transition-all border border-stone-200 rounded-lg px-2.5 py-1.5"
            >
              Lock
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-8 space-y-8">
        
        {/* Quick Add Bar & Upload controls */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* Quick-Add Box */}
          <div className="lg:col-span-2 bg-white border border-stone-200 shadow-premium rounded-2xl p-6 flex flex-col justify-center">
            <h2 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-neutral-400" /> Smart Command Add
            </h2>
            <form onSubmit={handleQuickAdd} className="relative flex items-center mt-1">
              <input 
                type="text" 
                value={quickAddQuery}
                onChange={(e) => setQuickAddQuery(e.target.value)}
                placeholder="Try: ₹250 coffee debit, or 12000 salary"
                className="w-full bg-stone-50 border border-stone-200 rounded-xl py-3.5 pl-4 pr-32 focus:outline-none focus:ring-2 focus:ring-neutral-950 focus:bg-white text-sm transition-all"
                disabled={quickAddLoading}
              />
              <div className="absolute right-2 flex items-center gap-1">
                <button
                  type="submit"
                  className="bg-neutral-950 hover:bg-neutral-800 text-white text-xs font-medium px-4 py-2 rounded-lg shadow-premium transition-all"
                  disabled={quickAddLoading}
                >
                  {quickAddLoading ? 'Adding...' : 'Add Row'}
                </button>
              </div>
            </form>
            <p className="text-[11px] text-neutral-400 mt-2 italic pl-1">
              Supports Rupee symbols, numbers, labels and tags out-of-the-box.
            </p>
          </div>

          {/* Statement Upload Box */}
          <div 
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className="border-2 border-dashed border-stone-200 bg-white hover:border-neutral-400 rounded-2xl p-6 text-center flex flex-col justify-center items-center cursor-pointer transition-all duration-300"
          >
            <input 
              type="file" 
              ref={fileInputRef}
              onChange={(e) => e.target.files?.[0] && handleFileUpload(e.target.files[0])}
              className="hidden"
              accept=".csv,.pdf"
            />
            {uploading ? (
              <div className="space-y-2">
                <div className="animate-spin w-8 h-8 border-2 border-neutral-900 border-t-transparent rounded-full mx-auto" />
                <p className="text-sm font-semibold text-neutral-700">Parsing statement...</p>
              </div>
            ) : (
              <div className="space-y-1.5">
                <UploadCloud className="w-8 h-8 text-neutral-400 mx-auto" />
                <p className="text-sm font-semibold text-neutral-800">Upload Statement</p>
                <p className="text-xs text-neutral-400">Drag & Drop bank PDF or CSV</p>
              </div>
            )}
            
            {uploadSuccess && (
              <p className="text-xs text-emerald-600 font-medium mt-2 bg-emerald-50 px-2 py-1 rounded">{uploadSuccess}</p>
            )}
            {uploadError && (
              <p className="text-xs text-rose-600 font-medium mt-2 bg-rose-50 px-2 py-1 rounded">{uploadError}</p>
            )}
          </div>
        </div>

        {/* Custom Column Schema Mapping Dialog */}
        {mappingRequired && (
          <div className="fixed inset-0 bg-neutral-950/20 backdrop-blur-sm flex items-center justify-center p-6 z-50 animate-fade-in font-sans">
            <div className="w-full max-w-2xl bg-white border border-stone-200 shadow-premium rounded-2xl p-8 space-y-6">
              <div className="flex items-center justify-between border-b pb-4">
                <div>
                  <h3 className="text-lg font-bold text-neutral-900">Map Statement Columns</h3>
                  <p className="text-xs text-neutral-500">Auto-detect failed. Please map the file columns to the standard format.</p>
                </div>
                <button onClick={() => setMappingRequired(false)} className="text-neutral-400 hover:text-neutral-600">
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Sample Headers View */}
              <div className="bg-stone-50 border p-4 rounded-xl space-y-2">
                <p className="text-xs font-semibold text-neutral-500 uppercase tracking-wider">File Columns Found</p>
                <div className="flex flex-wrap gap-2">
                  {mappingColumns.map(col => (
                    <span key={col} className="text-xs bg-white border px-2 py-1 rounded-md text-neutral-700">{col}</span>
                  ))}
                </div>
              </div>

              {/* Column Config selectors */}
              <div className="grid grid-cols-2 gap-4 text-sm font-sans">
                <div>
                  <label className="block text-xs font-semibold text-neutral-500 mb-1.5">Date Column *</label>
                  <select 
                    value={mappingConfig.date} 
                    onChange={e => setMappingConfig({...mappingConfig, date: e.target.value})}
                    className="w-full bg-stone-50 border p-2 rounded-lg"
                  >
                    <option value="">-- Select --</option>
                    {mappingColumns.map(col => <option key={col} value={col}>{col}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-neutral-500 mb-1.5">Description Column *</label>
                  <select 
                    value={mappingConfig.description} 
                    onChange={e => setMappingConfig({...mappingConfig, description: e.target.value})}
                    className="w-full bg-stone-50 border p-2 rounded-lg"
                  >
                    <option value="">-- Select --</option>
                    {mappingColumns.map(col => <option key={col} value={col}>{col}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-neutral-500 mb-1.5">Unified Amount (e.g. 500, -200)</label>
                  <select 
                    value={mappingConfig.amount} 
                    onChange={e => setMappingConfig({...mappingConfig, amount: e.target.value})}
                    className="w-full bg-stone-50 border p-2 rounded-lg"
                  >
                    <option value="">-- Select --</option>
                    {mappingColumns.map(col => <option key={col} value={col}>{col}</option>)}
                  </select>
                </div>
                <div className="border-l pl-4 space-y-3">
                  <p className="text-xs text-neutral-400 font-medium">Or Use Split Debit/Credit Columns:</p>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-[10px] font-semibold text-neutral-400 mb-1">Debit Column</label>
                      <select 
                        value={mappingConfig.debit} 
                        onChange={e => setMappingConfig({...mappingConfig, debit: e.target.value})}
                        className="w-full bg-stone-50 border p-1 rounded text-xs"
                      >
                        <option value="">-- Select --</option>
                        {mappingColumns.map(col => <option key={col} value={col}>{col}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="block text-[10px] font-semibold text-neutral-400 mb-1">Credit Column</label>
                      <select 
                        value={mappingConfig.credit} 
                        onChange={e => setMappingConfig({...mappingConfig, credit: e.target.value})}
                        className="w-full bg-stone-50 border p-1 rounded text-xs"
                      >
                        <option value="">-- Select --</option>
                        {mappingColumns.map(col => <option key={col} value={col}>{col}</option>)}
                      </select>
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex justify-end gap-3 border-t pt-4">
                <button 
                  onClick={() => setMappingRequired(false)} 
                  className="px-4 py-2 border rounded-lg text-sm text-neutral-500 hover:bg-stone-50"
                >
                  Cancel
                </button>
                <button 
                  onClick={submitCustomMapping}
                  className="px-4 py-2 bg-neutral-900 hover:bg-neutral-800 text-white rounded-lg text-sm shadow"
                >
                  Parse & Import
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Tab 1: Dashboard overview */}
        {activeTab === 'dashboard' && (
          <div className="space-y-8 animate-fade-in font-sans">
            
            {/* Overview Metric Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              
              {/* Income card */}
              <div className="bg-white border border-stone-200/80 shadow-premium rounded-2xl p-6 space-y-2 hover:shadow-premium-hover transition-all">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">Total Earnings</span>
                  <div className="w-8 h-8 rounded-full bg-emerald-50 flex items-center justify-center text-emerald-600">
                    <TrendingUp className="w-4 h-4" />
                  </div>
                </div>
                <div>
                  <h3 className="text-2xl font-bold tracking-tight text-neutral-950">₹{totals.income.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</h3>
                  <p className="text-xs text-neutral-400 mt-1">Sum of credit entries</p>
                </div>
              </div>

              {/* Expense card */}
              <div className="bg-white border border-stone-200/80 shadow-premium rounded-2xl p-6 space-y-2 hover:shadow-premium-hover transition-all">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">Total Spending</span>
                  <div className="w-8 h-8 rounded-full bg-amber-50 flex items-center justify-center text-amber-600">
                    <TrendingDown className="w-4 h-4" />
                  </div>
                </div>
                <div>
                  <h3 className="text-2xl font-bold tracking-tight text-neutral-950">₹{totals.expense.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</h3>
                  <p className="text-xs text-neutral-400 mt-1">Sum of debit entries</p>
                </div>
              </div>

              {/* Savings card */}
              <div className="bg-white border border-stone-200/80 shadow-premium rounded-2xl p-6 space-y-2 hover:shadow-premium-hover transition-all">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">Net Savings</span>
                  <div className="w-8 h-8 rounded-full bg-sky-50 flex items-center justify-center text-sky-600">
                    <DollarSign className="w-4 h-4" />
                  </div>
                </div>
                <div>
                  <h3 className="text-2xl font-bold tracking-tight text-neutral-950">₹{totals.net_savings.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</h3>
                  <div className="flex items-center gap-1 mt-1">
                    {predictions.savings_change_pct > 0 ? (
                      <span className="text-[10px] font-semibold text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded">+{predictions.savings_change_pct}% MoM</span>
                    ) : predictions.savings_change_pct < 0 ? (
                      <span className="text-[10px] font-semibold text-rose-600 bg-rose-50 px-1.5 py-0.5 rounded">{predictions.savings_change_pct}% MoM</span>
                    ) : (
                      <span className="text-[10px] text-neutral-400">Flat compared to last month</span>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Graphs Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              
              {/* Cash Flow Line/Area Chart */}
              <div className="lg:col-span-2 bg-white border border-stone-200 rounded-2xl p-6 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-neutral-900">Spending & Income Velocity</h3>
                    <p className="text-xs text-neutral-400">Cash flows observed over the last 30 days</p>
                  </div>
                </div>
                <div className="h-64">
                  {cashflowChart.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={cashflowChart} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                        <defs>
                          <linearGradient id="colorIncome" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#10b981" stopOpacity={0.15}/>
                            <stop offset="95%" stopColor="#10b981" stopOpacity={0.01}/>
                          </linearGradient>
                          <linearGradient id="colorExpense" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#ef4444" stopOpacity={0.15}/>
                            <stop offset="95%" stopColor="#ef4444" stopOpacity={0.01}/>
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                        <XAxis dataKey="name" stroke="#94a3b8" fontSize={10} tickLine={false} />
                        <YAxis stroke="#94a3b8" fontSize={10} tickLine={false} />
                        <Tooltip />
                        <Area type="monotone" dataKey="income" name="Income" stroke="#10b981" strokeWidth={2} fillOpacity={1} fill="url(#colorIncome)" />
                        <Area type="monotone" dataKey="expense" name="Expense" stroke="#ef4444" strokeWidth={2} fillOpacity={1} fill="url(#colorExpense)" />
                      </AreaChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="h-full flex items-center justify-center text-xs text-neutral-400">
                      No recent cash flow logs. Import statements to populate graphs.
                    </div>
                  )}
                </div>
              </div>

              {/* Category Breakdown Donut */}
              <div className="bg-white border border-stone-200 rounded-2xl p-6 space-y-4 flex flex-col justify-between">
                <div>
                  <h3 className="text-sm font-bold text-neutral-900">Category Allocation</h3>
                  <p className="text-xs text-neutral-400">Distribution of expenditures</p>
                </div>
                <div className="h-48 relative flex items-center justify-center">
                  {categoryChart.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={categoryChart}
                          cx="50%"
                          cy="50%"
                          innerRadius={50}
                          outerRadius={70}
                          paddingAngle={3}
                          dataKey="value"
                        >
                          {categoryChart.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={CATEGORY_COLORS[entry.name as keyof typeof CATEGORY_COLORS] || "#6b7280"} />
                          ))}
                        </Pie>
                        <Tooltip formatter={(value) => `₹${value}`} />
                      </PieChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="text-xs text-neutral-400">No category statistics.</div>
                  )}
                </div>
                
                {/* Custom Legends list */}
                <div className="grid grid-cols-2 gap-2 text-[10px] font-medium border-t pt-4">
                  {categoryChart.map(entry => (
                    <div key={entry.name} className="flex items-center gap-1.5 truncate">
                      <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: CATEGORY_COLORS[entry.name as keyof typeof CATEGORY_COLORS] || '#6b7280' }} />
                      <span className="text-neutral-600 truncate">{entry.name}</span>
                      <span className="font-semibold text-neutral-900 ml-auto">₹{entry.value.toLocaleString('en-IN')}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Predictions & AI Insights Section */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              
              {/* Projections & ML Line Trend */}
              <div className="lg:col-span-2 bg-white border border-stone-200 rounded-2xl p-6 space-y-6">
                <div>
                  <div className="flex items-center gap-1.5">
                    <h3 className="text-sm font-bold text-neutral-900">Savings Forecast Engine</h3>
                    <span className="text-[9px] uppercase tracking-wider font-semibold bg-indigo-50 border border-indigo-100 text-indigo-700 px-1.5 py-0.5 rounded">ML Linear Regression</span>
                  </div>
                  <p className="text-xs text-neutral-400">Estimated spending vs savings trends based on history</p>
                </div>

                <div className="grid grid-cols-2 gap-4 bg-stone-50 border p-4 rounded-xl text-sm font-sans">
                  <div>
                    <span className="block text-xs text-neutral-400">Projected EOM Expenses</span>
                    <span className="text-lg font-bold text-neutral-900">₹{predictions.projected_spend?.toLocaleString('en-IN') || 0}</span>
                  </div>
                  <div>
                    <span className="block text-xs text-neutral-400">Projected EOM Savings</span>
                    <span className={`text-lg font-bold ${predictions.projected_savings >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                      {predictions.projected_savings >= 0 ? '+' : ''}₹{predictions.projected_savings?.toLocaleString('en-IN') || 0}
                    </span>
                  </div>
                </div>

                <div className="h-48">
                  {predictions.forecast_chart?.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={predictions.forecast_chart} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                        <XAxis dataKey="name" stroke="#94a3b8" fontSize={9} />
                        <YAxis stroke="#94a3b8" fontSize={9} />
                        <Tooltip />
                        <Legend />
                        <Line type="monotone" dataKey="spending" name="Projected Spend" stroke="#ef4444" strokeWidth={2} dot={{ r: 4 }} />
                        <Line type="monotone" dataKey="savings" name="Projected Savings" stroke="#3b82f6" strokeWidth={2} dot={{ r: 4 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="h-full flex items-center justify-center text-xs text-neutral-400">
                      Import more months of data to plot forecast trends.
                    </div>
                  )}
                </div>
              </div>

              {/* Dynamic Insights Feed Column */}
              <div className="bg-white border border-stone-200 rounded-2xl p-6 space-y-4">
                <div>
                  <h3 className="text-sm font-bold text-neutral-900">AI Narrative Feed</h3>
                  <p className="text-xs text-neutral-400">Real-time pattern analysis and highlights</p>
                </div>
                
                <div className="space-y-4 max-h-[350px] overflow-y-auto pr-1">
                  {insights.map(item => (
                    <div 
                      key={item.id} 
                      className={`border p-4 rounded-xl space-y-1 transition-all hover:scale-[1.01] ${
                        item.type === 'warning' ? 'bg-amber-50/50 border-amber-200/80 text-amber-900' :
                        item.type === 'success' ? 'bg-emerald-50/50 border-emerald-200/80 text-emerald-950' :
                        'bg-stone-50 border-stone-200 text-neutral-800'
                      }`}
                    >
                      <div className="flex items-center gap-1.5">
                        <div className={`w-1.5 h-1.5 rounded-full ${
                          item.type === 'warning' ? 'bg-amber-500' :
                          item.type === 'success' ? 'bg-emerald-500' :
                          'bg-neutral-500'
                        }`} />
                        <h4 className="text-xs font-bold font-sans">{item.title}</h4>
                      </div>
                      <p className="text-xs leading-relaxed opacity-90 font-sans">{item.text}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Transactions Feed */}
        {activeTab === 'transactions' && (
          <div className="bg-white border border-stone-200 rounded-2xl p-6 space-y-6 animate-fade-in font-sans">
            
            {/* Filter toolbar */}
            <div className="flex flex-col md:flex-row gap-4 items-center justify-between border-b pb-4">
              <div className="flex flex-wrap gap-2 items-center w-full md:w-auto">
                
                {/* Search */}
                <div className="relative">
                  <Search className="w-4 h-4 text-neutral-400 absolute left-3 top-3" />
                  <input 
                    type="text" 
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search payee..."
                    className="pl-9 pr-4 py-2 border rounded-xl bg-stone-50 text-sm focus:outline-none focus:ring-2 focus:ring-neutral-900 focus:bg-white transition-all w-48 md:w-64"
                  />
                </div>

                {/* Category filter */}
                <select
                  value={selectedCategoryFilter}
                  onChange={(e) => setSelectedCategoryFilter(e.target.value)}
                  className="bg-stone-50 border rounded-xl px-3 py-2 text-sm text-neutral-600 focus:outline-none"
                >
                  <option value="">All Categories</option>
                  {CATEGORIES.map(cat => <option key={cat} value={cat}>{cat}</option>)}
                </select>

                {/* Type filter */}
                <select
                  value={selectedTypeFilter}
                  onChange={(e) => setSelectedTypeFilter(e.target.value)}
                  className="bg-stone-50 border rounded-xl px-3 py-2 text-sm text-neutral-600 focus:outline-none"
                >
                  <option value="">All Types</option>
                  <option value="debit">Expense</option>
                  <option value="credit">Income</option>
                </select>
              </div>

              <button 
                onClick={() => setShowAddModal(true)}
                className="bg-neutral-950 hover:bg-neutral-800 text-white text-xs font-semibold px-4 py-2.5 rounded-xl shadow flex items-center gap-1 text-center font-sans self-stretch md:self-auto"
              >
                <Plus className="w-3.5 h-3.5" /> New Transaction
              </button>
            </div>

            {/* Transactions lists table */}
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-sm">
                <thead>
                  <tr className="border-b text-neutral-400 font-semibold text-xs tracking-wider uppercase">
                    <th className="py-3 px-4">Date</th>
                    <th className="py-3 px-4">Description (Raw)</th>
                    <th className="py-3 px-4">Merchant (Clean)</th>
                    <th className="py-3 px-4 text-center">Category</th>
                    <th className="py-3 px-4 text-right">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map(tx => (
                    <tr key={tx.id} className="border-b hover:bg-stone-50/50 transition-colors group">
                      <td className="py-3.5 px-4 text-neutral-500 font-sans">
                        {new Date(tx.date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}
                      </td>
                      <td className="py-3.5 px-4 text-neutral-400 text-xs font-sans max-w-[200px] truncate" title={tx.raw_description}>
                        {tx.raw_description}
                      </td>
                      <td className="py-3.5 px-4 font-medium text-neutral-900 font-sans">
                        {tx.clean_description}
                      </td>
                      <td className="py-3.5 px-4 text-center">
                        {editingTxId === tx.id ? (
                          <div className="flex items-center justify-center gap-1">
                            <select 
                              value={editingCategory}
                              onChange={(e) => setEditingCategory(e.target.value)}
                              className="border p-1 text-xs rounded"
                            >
                              {CATEGORIES.map(cat => <option key={cat} value={cat}>{cat}</option>)}
                            </select>
                            <button 
                              onClick={() => saveCategoryOverride(tx.id)}
                              className="w-6 h-6 bg-emerald-50 text-emerald-600 rounded flex items-center justify-center hover:bg-emerald-100"
                            >
                              <Check className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        ) : (
                          <div className="flex items-center justify-center gap-1.5">
                            <span 
                              onClick={() => {
                                setEditingTxId(tx.id);
                                setEditingCategory(tx.category);
                              }}
                              className="text-xs font-medium px-2 py-0.5 rounded-full cursor-pointer hover:opacity-80 flex items-center gap-1 font-sans"
                              style={{ 
                                backgroundColor: (CATEGORY_COLORS[tx.category as keyof typeof CATEGORY_COLORS] || '#6b7280') + '15',
                                color: CATEGORY_COLORS[tx.category as keyof typeof CATEGORY_COLORS] || '#6b7280'
                              }}
                            >
                              {tx.category}
                              <Edit3 className="w-2.5 h-2.5 opacity-0 group-hover:opacity-100 transition-opacity ml-0.5 text-neutral-400" />
                            </span>
                            
                            {tx.is_ai_categorized && (
                              <span 
                                className="text-[9px] font-semibold text-indigo-600 bg-indigo-50 border border-indigo-100 px-1 rounded flex items-center gap-0.5"
                                title={`AI Predicted with ${Math.round(tx.confidence * 100)}% confidence`}
                              >
                                <Sparkles className="w-2 h-2" /> {Math.round(tx.confidence * 100)}%
                              </span>
                            )}
                          </div>
                        )}
                      </td>
                      <td className={`py-3.5 px-4 text-right font-semibold font-sans ${tx.type === 'credit' ? 'text-emerald-600' : 'text-neutral-900'}`}>
                        {tx.type === 'credit' ? '+' : '-'}₹{tx.amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </td>
                    </tr>
                  ))}

                  {transactions.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-xs text-neutral-400 font-sans">
                        No transactions found matching the parameters.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Tab 3: Categorization Rules */}
        {activeTab === 'rules' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-fade-in font-sans">
            
            {/* Create Rule Panel */}
            <div className="bg-white border border-stone-200 rounded-2xl p-6 space-y-4 self-start">
              <div>
                <h3 className="text-sm font-bold text-neutral-900">Define Categorization Rules</h3>
                <p className="text-xs text-neutral-400">Create rules to auto-assign categories based on merchant descriptors.</p>
              </div>

              <form onSubmit={handleAddRule} className="space-y-4 font-sans text-sm">
                <div>
                  <label className="block text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1.5">Merchant Pattern (Regex / Word)</label>
                  <input 
                    type="text" 
                    value={newRulePattern}
                    onChange={(e) => setNewRulePattern(e.target.value)}
                    placeholder="e.g. ZOMATO, SWIGGY, RENT"
                    className="w-full bg-stone-50 border p-2.5 rounded-lg focus:outline-none focus:ring-1 focus:ring-neutral-900"
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1.5">Target Category</label>
                  <select 
                    value={newRuleCategory}
                    onChange={(e) => setNewRuleCategory(e.target.value)}
                    className="w-full bg-stone-50 border p-2.5 rounded-lg focus:outline-none"
                  >
                    {CATEGORIES.map(cat => <option key={cat} value={cat}>{cat}</option>)}
                  </select>
                </div>

                <button 
                  type="submit"
                  className="w-full py-2.5 bg-neutral-900 hover:bg-neutral-800 text-white rounded-lg font-medium text-xs shadow transition-all"
                >
                  Create Rule
                </button>
              </form>
            </div>

            {/* Rules list feed */}
            <div className="lg:col-span-2 bg-white border border-stone-200 rounded-2xl p-6 space-y-4">
              <div>
                <h3 className="text-sm font-bold text-neutral-900">Active Rules</h3>
                <p className="text-xs text-neutral-400">Rules executed on matching descriptions before ML kicks in.</p>
              </div>

              <div className="space-y-2">
                {rules.map(rule => (
                  <div key={rule.id} className="flex items-center justify-between p-3 border rounded-xl hover:bg-stone-50 transition-all font-sans">
                    <div className="flex items-center gap-4">
                      <span className="font-semibold text-neutral-900 font-mono text-xs">{rule.pattern}</span>
                      <span className="text-xs px-2 py-0.5 rounded-full border text-neutral-600" style={{ borderColor: CATEGORY_COLORS[rule.target_category as keyof typeof CATEGORY_COLORS] + '50', backgroundColor: CATEGORY_COLORS[rule.target_category as keyof typeof CATEGORY_COLORS] + '09' }}>
                        {rule.target_category}
                      </span>
                    </div>
                    <button 
                      onClick={() => handleDeleteRule(rule.id)}
                      className="text-neutral-400 hover:text-rose-600 transition-colors w-7 h-7 flex items-center justify-center hover:bg-rose-50 rounded"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}

                {rules.length === 0 && (
                  <p className="text-xs text-neutral-400 text-center py-6">No custom rules declared. Add one above.</p>
                )}
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Traditional Structured New Transaction Dialog */}
      {showAddModal && (
        <div className="fixed inset-0 bg-neutral-950/20 backdrop-blur-sm flex items-center justify-center p-6 z-50 animate-fade-in font-sans">
          <div className="w-full max-w-md bg-white border border-stone-200 shadow-premium rounded-2xl p-8 space-y-6">
            <div className="flex items-center justify-between border-b pb-4">
              <h3 className="text-lg font-bold text-neutral-900">New Manual Transaction</h3>
              <button onClick={() => setShowAddModal(false)} className="text-neutral-400 hover:text-neutral-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleAddTx} className="space-y-4 font-sans text-sm">
              <div>
                <label className="block text-xs font-semibold text-neutral-500 mb-1">Date</label>
                <input 
                  type="date" 
                  value={newTx.date}
                  onChange={(e) => setNewTx({...newTx, date: e.target.value})}
                  className="w-full bg-stone-50 border p-2 rounded-lg"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-neutral-500 mb-1">Payee / Description</label>
                <input 
                  type="text" 
                  value={newTx.raw_description}
                  onChange={(e) => setNewTx({...newTx, raw_description: e.target.value})}
                  placeholder="e.g. Starbucks coffee"
                  className="w-full bg-stone-50 border p-2 rounded-lg"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-neutral-500 mb-1">Amount (₹)</label>
                  <input 
                    type="number" 
                    value={newTx.amount}
                    onChange={(e) => setNewTx({...newTx, amount: e.target.value})}
                    placeholder="e.g. 250"
                    className="w-full bg-stone-50 border p-2 rounded-lg"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-neutral-500 mb-1">Type</label>
                  <select 
                    value={newTx.type}
                    onChange={(e) => setNewTx({...newTx, type: e.target.value})}
                    className="w-full bg-stone-50 border p-2 rounded-lg"
                  >
                    <option value="debit">Expense</option>
                    <option value="credit">Income</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-neutral-500 mb-1">Category (Optional recommendation)</label>
                <select 
                  value={newTx.category}
                  onChange={(e) => setNewTx({...newTx, category: e.target.value})}
                  className="w-full bg-stone-50 border p-2 rounded-lg"
                >
                  {CATEGORIES.map(cat => <option key={cat} value={cat}>{cat}</option>)}
                </select>
              </div>

              <div className="flex gap-2 border-t pt-4 justify-end">
                <button 
                  type="button" 
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 border rounded-lg text-neutral-500 hover:bg-stone-50"
                >
                  Cancel
                </button>
                <button 
                  type="submit"
                  className="px-4 py-2 bg-neutral-900 hover:bg-neutral-800 text-white rounded-lg font-medium shadow"
                >
                  Save Transaction
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Footer copyright */}
      <footer className="bg-white border-t border-stone-200/80 py-6 text-center text-xs text-neutral-400 font-sans mt-auto">
        <p>© 2026 Ledgr AI. Built with React, Vite & FastAPI. Single User Mode.</p>
      </footer>
    </div>
  );
}
