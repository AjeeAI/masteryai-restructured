import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { AtSign, Headphones, MapPin, User, Badge, AlignLeft, Send } from 'lucide-react';

const fadeInUp = {
  hidden: { opacity: 0, y: 30 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6 } }
};

const staggerContainer = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.15 }
  }
};

const Contactpage = () => {
  const [formData, setFormData] = useState({
    fullName: '',
    studentId: '',
    subject: '',
    message: ''
  });

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    // Handle form submission logic here
    console.log('Form submitted:', formData);
    alert('Message sent successfully!');
    setFormData({ fullName: '', studentId: '', subject: '', message: '' });
  };

  const contactMethods = [
    {
      icon: <AtSign className="w-6 h-6 text-blue-600" />,
      label: 'EMAIL SUPPORT',
      value: 'masteryai@gmail.com'
    },
    {
      icon: <Headphones className="w-6 h-6 text-blue-600" />,
      label: 'ACADEMIC HOTLINE',
      value: '+234 800-000-0000'
    },
    {
      icon: <MapPin className="w-6 h-6 text-blue-600" />,
      label: 'OFFICE LOCATION',
      value: 'Online'
    }
  ];

  return (
    <div className="bg-slate-50 min-h-screen py-16 lg:py-24">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid lg:grid-cols-2 gap-16 items-start">
          
          {/* Left Column: Contact Info */}
          <motion.div 
            initial="hidden" 
            animate="visible" 
            variants={staggerContainer}
            className="flex flex-col space-y-8"
          >
            <motion.div variants={fadeInUp}>
              <h1 className="text-5xl font-serif italic text-slate-900 mb-6">
                Get in Touch
              </h1>
              <p className="text-slate-600 text-lg max-w-md leading-relaxed">
                Dedicated academic assistance for SSS1-SSS3 students and parents. 
                Our AI Personalized Tutor is ready to guide your learning journey.
              </p>
            </motion.div>

            <div className="space-y-4">
              {contactMethods.map((method, idx) => (
                <motion.div 
                  key={idx} 
                  variants={fadeInUp}
                  className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 flex items-center gap-6 hover:shadow-md transition-shadow"
                >
                  <div className="bg-blue-50 p-4 rounded-full shrink-0">
                    {method.icon}
                  </div>
                  <div>
                    <p className="text-blue-600 text-xs font-bold tracking-wider mb-1 uppercase">
                      {method.label}
                    </p>
                    <p className="text-slate-900 font-semibold text-lg">
                      {method.value}
                    </p>
                  </div>
                </motion.div>
              ))}
            </div>

            {/* Map/Campus Image Card */}
            <motion.div 
              variants={fadeInUp}
              className="relative h-48 rounded-3xl overflow-hidden shadow-sm border border-slate-200"
            >
              <img 
                src="https://images.unsplash.com/photo-1524661135-423995f22d0b?auto=format&fit=crop&w=800&q=80" 
                alt="Campus Map" 
                className="w-full h-full object-cover"
              />
              <div className="absolute inset-0 bg-linear-to-t from-black/60 to-transparent"></div>
              <div className="absolute bottom-4 left-6 flex items-center gap-3">
                <span className="relative flex h-3 w-3">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-blue-500"></span>
                </span>
                <span className="text-white font-bold text-sm tracking-widest uppercase">
                  VISIT OUR CAMPUS
                </span>
              </div>
            </motion.div>
          </motion.div>

          {/* Right Column: Contact Form */}
          <motion.div 
            initial={{ opacity: 0, x: 40 }} 
            animate={{ opacity: 1, x: 0 }} 
            transition={{ duration: 0.7, delay: 0.2 }}
          >
            <div className="bg-white p-8 md:p-10 rounded-[2.5rem] shadow-[0_8px_30px_rgb(0,0,0,0.04)] border border-slate-100">
              <h2 className="text-2xl font-bold text-slate-900 mb-2">Send us a Message</h2>
              <p className="text-slate-500 text-sm mb-8">
                Fill out the form below and our team will get back to you within 24 hours.
              </p>

              <form onSubmit={handleSubmit} className="space-y-6">
                
                {/* 2-Column Row */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <label className="text-sm font-semibold text-slate-700">Full Name</label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                        <User className="h-5 w-5 text-slate-400" />
                      </div>
                      <input 
                        type="text" 
                        name="fullName"
                        value={formData.fullName}
                        onChange={handleChange}
                        placeholder="e.g. Chinelo Adebayo" 
                        className="w-full pl-11 pr-4 py-3.5 bg-slate-50 border-none rounded-xl text-sm focus:ring-2 focus:ring-blue-600 focus:bg-white transition-colors"
                        required
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-semibold text-slate-700">Student ID (SSS ID)</label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                        <Badge className="h-5 w-5 text-slate-400" />
                      </div>
                      <input 
                        type="text" 
                        name="studentId"
                        value={formData.studentId}
                        onChange={handleChange}
                        placeholder="SSS-24-XXXX" 
                        className="w-full pl-11 pr-4 py-3.5 bg-slate-50 border-none rounded-xl text-sm focus:ring-2 focus:ring-blue-600 focus:bg-white transition-colors"
                      />
                    </div>
                  </div>
                </div>

                {/* Subject Field */}
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-slate-700">Subject</label>
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                      <AlignLeft className="h-5 w-5 text-slate-400" />
                    </div>
                    <input 
                      type="text" 
                      name="subject"
                      value={formData.subject}
                      onChange={handleChange}
                      placeholder="Enter inquiry category" 
                      className="w-full pl-11 pr-4 py-3.5 bg-slate-50 border-none rounded-xl text-sm focus:ring-2 focus:ring-blue-600 focus:bg-white transition-colors"
                      required
                    />
                  </div>
                </div>

                {/* Message Textarea */}
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-slate-700">Message</label>
                  <textarea 
                    name="message"
                    value={formData.message}
                    onChange={handleChange}
                    placeholder="Describe how we can assist you..." 
                    rows="5"
                    className="w-full p-4 bg-slate-50 border-none rounded-xl text-sm focus:ring-2 focus:ring-blue-600 focus:bg-white transition-colors resize-none"
                    required
                  ></textarea>
                </div>

                {/* Submit Button */}
                <button 
                  type="submit"
                  className="w-full bg-[#0a66c2] hover:bg-blue-700 text-white font-medium py-4 rounded-xl flex items-center justify-center gap-2 transition-all duration-800 shadow-md hover:shadow-lg cursor-pointer hover:scale-95"
                >
                  Send Message <Send className="h-4 w-4" />
                </button>

                {/* Privacy Disclaimer */}
                <p className="text-center text-xs text-slate-400 mt-4">
                  By submitting this form, you agree to our <a href="#" className="text-blue-600 hover:underline">Privacy Policy</a>
                </p>

              </form>
            </div>
          </motion.div>

        </div>
      </div>
    </div>
  );
};

export default Contactpage;