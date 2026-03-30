import React from 'react';
import { motion } from 'framer-motion';
import { 
  ShieldCheck, Database, Users, Eye, Lightbulb, Heart 
} from 'lucide-react';

const fadeInUp = {
  hidden: { opacity: 0, y: 40 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6 } }
};

const AboutPage = () => {
  return (
    <div className="overflow-hidden bg-white">
      {/* Hero Section */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="grid lg:grid-cols-2 gap-16 items-center">
          <motion.div initial="hidden" animate="visible" variants={fadeInUp}>
            <div className="text-blue-600 font-semibold tracking-wider text-sm mb-4 uppercase">
              Our Vision
            </div>
            <h1 className="text-5xl font-extrabold text-slate-900 leading-tight mb-6">
              Revolutionizing <br/>Education Through <br/>
              <span className="text-blue-600">Intelligence</span>
            </h1>
            <p className="text-lg text-slate-600 max-w-lg">
              We are building the future of learning for Secondary Schools. By harnessing the power of adaptive AI, we bridge the gap between potential and performance for every student.
            </p>
          </motion.div>
          
          <motion.div 
            initial={{ opacity: 0, scale: 0.9 }} 
            animate={{ opacity: 1, scale: 1 }} 
            transition={{ duration: 0.6, delay: 0.2 }}
            className="relative rounded-3xl overflow-hidden shadow-2xl bg-linear-to-tr from-slate-900 to-slate-800 p-2"
          >
            <img 
              src="https://res.cloudinary.com/ddnxhqqkq/image/upload/v1772408293/Gemini_Generated_Image_dpi669dpi669dpi6_m8bpzq.png" 
              alt="Students learning" 
              className="rounded-2xl w-full h-auto object-cover opacity-80"
            />
            <div className="absolute bottom-6 left-6 bg-white/10 backdrop-blur-md border border-white/20 p-4 rounded-xl flex items-center gap-4 text-white">
              <div className="bg-blue-500 p-2 rounded-full">
                <Users className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm font-semibold">Over 15k+ active students</p>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Mission Section */}
      <section className="bg-slate-900 text-white py-24">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <motion.div initial="hidden" whileInView="visible" viewport={{ once: true }} variants={fadeInUp} className="text-center mb-16">
            <h2 className="text-3xl font-bold mb-4">Our Mission</h2>
            <p className="text-slate-400 max-w-2xl mx-auto">
              To bridge the educational divide by leveraging artificial intelligence to deliver world-class, individualized tutoring to every learner, regardless of background.
            </p>
          </motion.div>

          <div className="grid md:grid-cols-3 gap-8">
            {[
              { icon: <ShieldCheck />, title: 'Closing Knowledge Gaps', desc: 'Our AI identifies subtle misunderstandings in foundational concepts early, preventing them from becoming major roadblocks in senior secondary education.' },
              { icon: <Database />, title: 'Data-Driven Equity', desc: "We democratize access to high-quality tutoring. Every student, regardless of their school's resources, gets world-class adaptive learning support." },
              { icon: <Users />, title: 'Parent & School Synergy', desc: 'We create a transparent ecosystem where parents, teachers, and students are aligned on goals, progress, and areas needing improvement.' }
            ].map((card, idx) => (
              <motion.div 
                key={idx} 
                initial="hidden" 
                whileInView="visible" 
                viewport={{ once: true }} 
                variants={{ hidden: { opacity: 0, y: 30 }, visible: { opacity: 1, y: 0, transition: { delay: idx * 0.2 } } }}
                className="bg-slate-800 p-8 rounded-2xl border border-slate-700 hover:-translate-y-2 transition-transform duration-300"
              >
                <div className="text-blue-400 mb-6">{React.cloneElement(card.icon, { className: 'h-8 w-8' })}</div>
                <h3 className="text-xl font-bold mb-3">{card.title}</h3>
                <p className="text-slate-400 text-sm leading-relaxed">{card.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Core Values */}
      <section className="bg-slate-50 py-24">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold text-slate-900">Our Core Values</h2>
          </div>
          
          <div className="grid md:grid-cols-3 gap-8">
            {[
              { icon: <Eye />, title: 'Transparency', color: 'text-blue-600', bg: 'bg-blue-100', desc: 'We believe in open communication with schools and parents. Our algorithms and pricing are clear, with no hidden fees or black-box grading.' },
              { icon: <Lightbulb />, title: 'Innovation', color: 'text-orange-600', bg: 'bg-orange-100', desc: 'We continuously push the boundaries of EdTech. From adaptive learning paths to AI-driven insights, we never stop improving.' },
              { icon: <Heart />, title: 'Student-First', color: 'text-green-600', bg: 'bg-green-100', desc: 'Every decision we make starts with one question: "Does this help the student learn better?" Your success is our north star.' }
            ].map((value, idx) => (
              <motion.div 
                key={idx} 
                initial="hidden" 
                whileInView="visible" 
                viewport={{ once: true }} 
                variants={fadeInUp}
                className="bg-white p-10 rounded-3xl shadow-sm border border-slate-100 text-center hover:shadow-xl transition-shadow duration-300"
              >
                <div className={`mx-auto w-16 h-16 ${value.bg} ${value.color} rounded-2xl flex items-center justify-center mb-6`}>
                  {React.cloneElement(value.icon, { className: 'h-8 w-8' })}
                </div>
                <h3 className="text-xl font-bold text-slate-900 mb-4">{value.title}</h3>
                <p className="text-slate-600 text-sm">{value.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Leadership & Team */}
      <section className="py-24 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-16">
          <h2 className="text-3xl font-bold text-slate-900 mb-4">Leadership & Team</h2>
          <p className="text-slate-600">Meet the educators, technologists, and visionaries dedicated to redefining secondary education through adaptive intelligence.</p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-8">
          {[
            { name: 'Saheed Olayinka', role: 'Team Lead/AI Engineering Lead', img: 'https://res.cloudinary.com/dzt3imk5w/image/upload/v1772798203/WhatsApp_Image_2026-03-04_at_9.54.02_PM_1_j7gr3n.jpg' },
            { name: 'Ajijolaoluwa Adesoji', role: 'Co-Team Lead/AI Development Lead', img: 'https://res.cloudinary.com/dzt3imk5w/image/upload/v1772803812/IMG_20260306_133457_xsem0i.jpg' },
            { name: 'Olusola Somorin', role: 'AI Developer/ UI/UX Designer', img: 'https://res.cloudinary.com/dzt3imk5w/image/upload/v1772803813/IMG_20260306_133349_bp73pp.jpg' },
            { name: 'Favour Olaoshebikan', role: 'AI Developer', img: 'https://res.cloudinary.com/dzt3imk5w/image/upload/v1772798204/WhatsApp_Image_2026-03-05_at_6.12.37_AM_bad9aq.jpg' },
            { name: 'Gbolahan', role: 'AI Developer', img: 'https://res.cloudinary.com/dzt3imk5w/image/upload/v1772798203/WhatsApp_Image_2026-03-05_at_10.58.47_AM_1_q8ykgg.jpg' },
            { name: 'Adebimpe Atoyebi', role: 'AI Developer', img: 'https://res.cloudinary.com/dzt3imk5w/image/upload/v1772798203/WhatsApp_Image_2026-03-04_at_9.55.51_PM_1_y8j5xg.jpg' },
            // Add two more real team members here to make it a perfect 8!
            { name: 'Olajide Abioye', role: 'AI Engineer', img: 'https://res.cloudinary.com/dzt3imk5w/image/upload/v1772798204/WhatsApp_Image_2026-03-04_at_9.46.26_PM_1_jx4dcx.jpg' },
            { name: 'Mary Adeoye', role: 'AI Engineer', img: 'https://res.cloudinary.com/dzt3imk5w/image/upload/v1772798204/WhatsApp_Image_2026-03-04_at_9.51.24_PM_1_ibxkks.jpg' },
            { name: 'Esther Kudoro', role: 'AI Engineer', img: 'https://res.cloudinary.com/dzt3imk5w/image/upload/v1772800096/ricus-_2-of-14_djbgo2.jpg' },

          ].map((member, idx) => (
            <motion.div 
              key={idx} 
              initial="hidden" 
              whileInView="visible" 
              viewport={{ once: true }} 
              variants={fadeInUp}
              className="bg-white border border-slate-200 p-8 rounded-3xl text-center hover:-translate-y-2 transition-transform duration-300"
            >
              <img src={member.img} alt={member.name} className="w-24 h-24 rounded-full mx-auto mb-6 object-cover border-4 border-slate-100" />
              <h4 className="font-bold text-slate-900">{member.name}</h4>
              <p className="text-xs font-bold text-blue-600 mt-1 mb-4">{member.role}</p>
              <p className="text-xs text-slate-500"></p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Join CTA */}
      <section className="pb-24 max-w-5xl mx-auto px-4">
        <motion.div 
          initial="hidden" 
          whileInView="visible" 
          viewport={{ once: true }} 
          variants={fadeInUp}
          className="bg-slate-900 rounded-3xl p-12 text-center text-white shadow-2xl"
        >
          <h2 className="text-3xl font-bold mb-4">Join the Revolution</h2>
          <p className="text-slate-400 mb-8 max-w-xl mx-auto">
            Whether you are a school administrator looking to boost results, or a parent seeking the best for your child, MasteryAI is your partner in excellence.
          </p>
          <div className="flex flex-wrap justify-center gap-4">
            <button className="bg-blue-600 hover:bg-blue-700 text-white px-8 py-3 rounded-full font-medium transition-all">
              Subscribe
            </button>
            <button className="bg-transparent border border-slate-600 hover:border-white text-white px-8 py-3 rounded-full font-medium transition-all">
              Contact Us
            </button>
          </div>
        </motion.div>
      </section>
    </div>
  );
};

export default AboutPage;