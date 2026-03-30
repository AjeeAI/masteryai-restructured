import React from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { 
  PlayCircle, AlertTriangle, Target, BookOpen, 
  Settings, TrendingUp, Award, Shield, UserCheck, Layout, ArrowRight
} from 'lucide-react';

const fadeInUp = {
  hidden: { opacity: 0, y: 40 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6 } }
};

const HomePage = () => {
  return (
    <div className="overflow-hidden">
      {/* Hero Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 lg:py-24">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          <motion.div initial="hidden" animate="visible" variants={fadeInUp}>
            <div className="inline-block bg-blue-100 text-blue-700 px-3 py-1 rounded-full text-sm font-semibold mb-6">
              Empowering African Students
            </div>
            <h1 className="text-5xl lg:text-6xl font-extrabold text-slate-900 leading-tight mb-6">
              Personalized AI Tutor <br/> for <span className="text-blue-600">SSS1-SSS3</span>
            </h1>
            <p className="text-lg text-slate-600 mb-8 max-w-lg">
              Unlock your true potential with our intelligent AI tutor. Master your subjects and ace your WAEC & JAMB exams with ease.
            </p>
            <div className="flex flex-wrap gap-4">
              <Link 
                to="/register" 
                className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-3.5 rounded-full font-medium transition-all shadow-lg cursor-pointer hover:shadow-blue-500/30 hover:scale-105 duration-1000 inline-block text-center"
              >
                Request a demo
              </Link>
              <Link 
                to="/about" 
                className="flex items-center justify-center gap-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 px-8 py-3.5 rounded-full font-medium cursor-pointer transition-all hover:scale-105 duration-1000"
              >
                <PlayCircle className="h-5 w-5" /> See how it works
              </Link>
            </div>
          </motion.div>
          <motion.div 
            initial={{ opacity: 0, scale: 0.9 }} 
            animate={{ opacity: 1, scale: 1 }} 
            transition={{ duration: 0.6, delay: 0.2 }}
            className="relative"
          >
            {/* Dashboard Mockup Image */}
            <div className="bg-slate-800 rounded-2xl p-4 shadow-2xl border border-slate-700 transform rotate-1 hover:rotate-0 transition-transform duration-500">
              <img 
                src="https://res.cloudinary.com/dzt3imk5w/image/upload/v1772805067/Screenshot_2026-03-02_130112_uyj6db.png" 
                alt="AI Dashboard" 
                className="rounded-xl w-full h-auto object-cover opacity-90"
              />
            </div>
          </motion.div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="border-y border-slate-200 bg-white">
        <div className="max-w-7xl mx-auto px-4 py-10">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
            {[
              { number: '15k+', label: 'Students Supported' },
              { number: '50+', label: 'Partner Schools' },
              { number: '98%', label: 'Success Rate' },
              { number: '24/7', label: 'AI Tutor Access' }
            ].map((stat, idx) => (
              <motion.div key={idx} initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeInUp}>
                <h3 className="text-4xl font-bold text-slate-900 mb-2">{stat.number}</h3>
                <p className="text-sm text-slate-500 font-medium uppercase tracking-wider">{stat.label}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Overcoming Gaps */}
      <section className="py-24 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid lg:grid-cols-2 gap-16 items-center">
          <motion.div initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeInUp}>
            <h2 className="text-3xl font-bold text-slate-900 mb-6">Overcoming Learning Gaps & Pressure</h2>
            <p className="text-slate-600 mb-8">
              Traditional education often fails to address individual learning gaps, putting immense pressure on students preparing for major exams.
            </p>
            <div className="space-y-6">
              <div className="flex gap-4">
                <div className="bg-red-100 p-3 rounded-lg h-fit">
                  <AlertTriangle className="h-6 w-6 text-red-600" />
                </div>
                <div>
                  <h4 className="font-semibold text-slate-900">Knowledge Gaps</h4>
                  <p className="text-slate-600 text-sm mt-1">Students move to new topics without mastering foundational concepts.</p>
                </div>
              </div>
              <div className="flex gap-4">
                <div className="bg-orange-100 p-3 rounded-lg h-fit">
                  <TrendingUp className="h-6 w-6 text-orange-600" />
                </div>
                <div>
                  <h4 className="font-semibold text-slate-900">Exam Anxiety</h4>
                  <p className="text-slate-600 text-sm mt-1">The sheer volume of material to cover causes stress and burnout.</p>
                </div>
              </div>
            </div>
          </motion.div>
          
          <motion.div 
            initial={{ opacity: 0, x: 50 }} 
            whileInView={{ opacity: 1, x: 0 }} 
            viewport={{ once: true }}
            className="bg-white p-8 rounded-3xl shadow-xl border border-slate-100"
          >
            <h3 className="text-xl font-bold mb-6">Intelligent Concept Mapping</h3>
            <p className="text-slate-600 mb-6 text-sm">We analyze weaknesses instantly and build a personalized path to mastery.</p>
            
            <div className="space-y-4">
              <div className="bg-blue-50 border border-blue-100 p-4 rounded-xl flex gap-4 items-start">
                <Target className="h-5 w-5 text-blue-600 mt-0.5" />
                <div>
                  <h5 className="font-semibold text-sm text-slate-900">Personalized Pacing</h5>
                  <p className="text-xs text-slate-500 mt-1">Learn at a speed tailored to your exact comprehension level.</p>
                </div>
              </div>
              <div className="bg-green-50 border border-green-100 p-4 rounded-xl flex gap-4 items-start">
                <BookOpen className="h-5 w-5 text-green-600 mt-0.5" />
                <div>
                  <h5 className="font-semibold text-sm text-slate-900">Curriculum Aligned</h5>
                  <p className="text-xs text-slate-500 mt-1">Strictly follows the approved syllabus to ensure exam readiness.</p>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* How It Works */}
      <section className="bg-slate-100 py-24">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <motion.h2 initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeInUp} className="text-3xl font-bold text-slate-900 mb-16">
            How It Works
          </motion.h2>
          
          <div className="grid md:grid-cols-4 gap-8 relative">
            {/* Connecting Line */}
            <div className="hidden md:block absolute top-8 left-1/8 right-1/8 h-0.5 bg-slate-300 z-0"></div>
            
            {[
              { icon: <Settings />, title: '1. Assessment', desc: 'Identify baseline knowledge' },
              { icon: <Target />, title: '2. Personalization', desc: 'Custom learning pathways' },
              { icon: <BookOpen />, title: '3. Learning', desc: 'Interactive AI-guided sessions' },
              { icon: <Award />, title: '4. Mastery', desc: 'Track progress to excellence' }
            ].map((step, idx) => (
              <motion.div 
                key={idx} 
                initial="hidden" 
                whileInView="visible" 
                viewport={{ once: true }} 
                variants={{ hidden: { opacity: 0, y: 30 }, visible: { opacity: 1, y: 0, transition: { delay: idx * 0.2 } } }}
                className="relative z-10 flex flex-col items-center"
              >
                <div className="bg-white p-4 rounded-full shadow-md text-blue-600 mb-6 border-4 border-slate-100">
                  {React.cloneElement(step.icon, { className: 'h-6 w-6' })}
                </div>
                <h4 className="font-bold text-slate-900 mb-2">{step.title}</h4>
                <p className="text-sm text-slate-600">{step.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Partners & Governance */}
      <section className="py-24 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        
        {/* Partners Header & Pills */}
        <div className="text-center mb-12">
          <p className="text-green-600 font-semibold tracking-wider text-sm mb-3 uppercase">
            Our Partners
          </p>
          <h2 className="text-3xl font-bold text-slate-900 mb-4">
            Partners & Governance
          </h2>
          <p className="text-slate-600 max-w-2xl mx-auto mb-10">
            Collaborating with leading educational bodies and top-tier institutions to set the standard for digital learning in West Africa.
          </p>
          
          <div className="flex flex-wrap justify-center gap-4 mb-16">
            {['WAEC', 'JAMB', 'Ministries', 'Private Schools', 'Public Schools', 'EdTech'].map((partner, idx) => (
              <div key={idx} className="bg-white border border-slate-200 text-slate-500 px-6 py-3 rounded-xl font-medium shadow-sm hover:shadow-md transition-shadow text-sm">
                {partner}
              </div>
            ))}
          </div>
        </div>

        <motion.div 
          initial="hidden" 
          whileInView="visible" 
          viewport={{ once: true }} 
          variants={fadeInUp}
          className="bg-[#0f172a] rounded-3xl p-10 md:p-16 text-white shadow-2xl relative overflow-hidden"
        >
          {/* Decorative gradients */}
          <div className="absolute top-0 right-0 w-96 h-96 bg-blue-600 rounded-full mix-blend-multiply filter blur-3xl opacity-20"></div>
          
          <div className="relative z-10 grid lg:grid-cols-5 gap-12 items-center">
            
            {/* Left Column */}
            <div className="lg:col-span-2">
              <div className="inline-block border border-slate-700 bg-slate-800 text-green-300 px-3 py-1 rounded-full text-xs font-semibold mb-6">
                SAFETY FIRST
              </div>
              <h2 className="text-3xl font-bold mb-4">Responsible AI Governance</h2>
              <p className="text-slate-400 mb-8 text-sm leading-relaxed">
                Our AI models are rigorously trained on approved curriculums only. We prioritize student data privacy and algorithmic fairness to ensure a safe, bias-free learning environment.
              </p>
              <button className="text-white font-medium hover:text-slate-300 flex items-center gap-2 text-sm border-b border-white pb-1 w-fit cursor-pointer">
                Read our Privacy Policy <ArrowRight className="h-4 w-4" />
              </button>
            </div>
            
            {/* Right Column Grid */}
            <div className="lg:col-span-3 grid sm:grid-cols-2 gap-8">
              {[
                { 
                  title: 'Curriculum Aligned', 
                  desc: 'Content strictly follows NERDC guidelines for SSS1-3, ensuring no hallucinations or out-of-scope material.',
                  icon: <BookOpen className="h-5 w-5 text-blue-400" />,
                  bg: 'bg-blue-900/30 border-blue-800/50'
                },
                { 
                  title: 'Data Privacy', 
                  desc: 'Enterprise-grade encryption for all student data, fully compliant with NDPR regulations.',
                  icon: <Shield className="h-5 w-5 text-green-400" />,
                  bg: 'bg-green-900/30 border-green-800/50'
                },
                { 
                  title: 'Human in the Loop', 
                  desc: 'Every AI-generated learning path is periodically reviewed by expert educators.',
                  icon: <UserCheck className="h-5 w-5 text-orange-400" />,
                  bg: 'bg-orange-900/30 border-orange-800/50'
                },
                { 
                  title: 'Inclusive Design', 
                  desc: 'Features designed to support diverse learning needs and accessibility standards.',
                  icon: <Layout className="h-5 w-5 text-purple-400" />,
                  bg: 'bg-purple-900/30 border-purple-800/50'
                }
              ].map((item, idx) => (
                <div key={idx} className="bg-transparent">
                  <div className={`w-10 h-10 rounded-lg flex items-center justify-center mb-4 border ${item.bg}`}>
                    {item.icon}
                  </div>
                  <h4 className="font-semibold mb-2 text-white">{item.title}</h4>
                  <p className="text-slate-400 text-xs leading-relaxed">{item.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </motion.div>

        {/* Action Buttons Below Governance */}
        <motion.div
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true }}
          variants={fadeInUp}
          className="flex justify-center gap-4 mt-10"
        >
          <Link 
            to="/about" 
            className="inline-block bg-white text-slate-700 border border-slate-200 px-6 py-2.5 rounded-full font-semibold hover:bg-blue-700 hover:text-white transform hover:scale-105 duration-1000 transition-all cursor-pointer text-sm shadow-sm"
          >
            Learn more
          </Link>
          <Link 
            to="#" 
            className="inline-flex bg-white text-slate-700 border border-slate-200 px-6 py-2.5 rounded-full font-semibold text-sm shadow-sm items-center gap-2 hover:bg-blue-700 hover:text-white transform hover:scale-105 duration-1000 transition-all cursor-pointer"
          >
            View pricing <ArrowRight className="h-4 w-4 text-slate-400" />
          </Link>
        </motion.div>

        {/* CTA Banner */}
        <motion.div 
          initial="hidden" 
          whileInView="visible" 
          viewport={{ once: true }} 
          variants={fadeInUp}
          className="mt-20 bg-blue-600 rounded-3xl p-10 flex flex-col md:flex-row items-center justify-between text-white shadow-xl"
        >
          <div>
            <h2 className="text-3xl font-bold mb-2">Ready to transform learning?</h2>
            <p className="text-blue-100">Join thousands of students and schools upgrading their education today.</p>
          </div>
          <Link 
            to="/register" 
            className="mt-6 md:mt-0 inline-block text-center bg-white text-blue-600 px-8 py-4 rounded-full font-bold shadow-lg hover:shadow-xl hover:-translate-y-1 transition-all whitespace-nowrap transform hover:scale-105 duration-1000 cursor-pointer"
          >
            Get Started Now
          </Link>
        </motion.div>
      </section>
    </div>
  );
};

export default HomePage;